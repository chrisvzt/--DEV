import csv
import html
import os
from urllib.parse import quote, unquote

import requests
import urllib3
from requests.auth import HTTPBasicAuth


# Suppress warnings because SSL verification is temporarily disabled.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

XWIKI_BASE_URL = "https://wikistage.llts.com:8181/xwiki"
XWIKI_WIKI_NAME = "xwiki"
USERNAME = "chvezinet"

# Set this in PowerShell before running the script:
#
# $env:XWIKI_PASSWORD = "your-password"
#
PASSWORD = os.environ.get("XWIKI_PASSWORD")

CLASS_NAME = "ClientInfoLibraryCode.ClientInfoLibraryClass"
SPACE = "Client Info Library"

# Scan this many successful CIL records.
INVENTORY_LIMIT = 500

# Number of candidate pages retrieved from XWiki per query.
QUERY_BATCH_SIZE = 100


ATTACHMENT_INVENTORY_FILE = "cil_attachment_inventory.csv"
CLIENT_SUMMARY_FILE = "cil_client_attachment_summary.csv"
SKIPPED_FILE = "cil_inventory_skipped_pages.csv"
ERROR_FILE = "cil_inventory_errors.csv"


FIELDS = [
    "Business_System",
    "clientname",
    "parentcompany",
    "childcompany",
    "lead",
    "pmlead",
    "notesissues",
    "intake",
    "cid",
    "legalentity",
    "requirequote",
    "whoapprovequote",
    "refusingprojects",
    "followrules",
    "intakeinfo",
    "processingrequirements",
    "securityrequirements",
    "translationmemory",
    "translationglossary",
    "usrequirements",
    "deliveryrequirements",
    "certificationneeded",
    "preferredlinguist",
    "processinginformation",
    "pricingrequirements",
    "pricingstructure",
    "expandoncontract",
    "rushfees",
    "minimums",
    "languagenotincluded",
    "billclient",
    "porequirements",
    "billingcontact",
    "billinginfo",
]


# ---------------------------------------------------------------------------
# Validation and session setup
# ---------------------------------------------------------------------------

if not PASSWORD:
    raise RuntimeError(
        "The XWIKI_PASSWORD environment variable is not set.\n\n"
        "In the VS Code PowerShell terminal, run:\n\n"
        '$env:XWIKI_PASSWORD = "your-password"\n\n'
        "Then run this script again."
    )


session = requests.Session()

# Temporary workaround for the internal XWiki certificate.
# Later, this should be replaced with the company CA certificate.
session.verify = False

session.auth = HTTPBasicAuth(
    USERNAME,
    PASSWORD,
)

session.headers.update(
    {
        "Accept": "application/json",
    }
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class NonCILPageError(Exception):
    """
    Raised when a page exists but does not contain a CIL data object.
    """


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def safe_integer(value):
    """
    Convert a value into an integer where possible.
    """

    if value in (None, ""):
        return 0

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def write_csv(filename, fieldnames, rows):
    """
    Write CSV data in a format that opens cleanly in Excel.
    """

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as output:
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


def find_link(item, relation_suffix):
    """
    Find a link whose rel property ends with a particular suffix.

    Examples:
        /objects
        /object
        /properties
        /attachments
        /attachment
    """

    links = item.get("links", [])

    if isinstance(links, dict):
        links = [links]

    for link in links:
        if not isinstance(link, dict):
            continue

        href = link.get("href", "")
        relation = link.get("rel", "")

        if href and relation.endswith(relation_suffix):
            return href

    return None


def build_page_url(page):
    """
    Build the REST page URL from the exact page name returned by XWiki.
    """

    space = page.get("space", SPACE)
    page_name = page.get("page_name", "")

    if not page_name:
        raise ValueError(
            "XWiki returned no pageName for "
            f"{page.get('page_full_name', '(unknown page)')!r}."
        )

    space_encoded = quote(
        space,
        safe="",
    )

    page_encoded = quote(
        page_name,
        safe="",
    )

    return (
        f"{XWIKI_BASE_URL}/rest/wikis/{XWIKI_WIKI_NAME}/"
        f"spaces/{space_encoded}/pages/{page_encoded}"
    )


# ---------------------------------------------------------------------------
# Page queries
# ---------------------------------------------------------------------------

def get_page_batch(start):
    """
    Retrieve one batch of visible Client Info Library pages.
    """

    url = (
        f"{XWIKI_BASE_URL}/rest/wikis/"
        f"{XWIKI_WIKI_NAME}/query"
    )

    query = f"""
where doc.space = '{SPACE}'
and doc.hidden = 0
"""

    params = {
        "q": query,
        "type": "hql",
        "number": QUERY_BATCH_SIZE,
        "start": start,
    }

    response = session.get(
        url,
        params=params,
        timeout=60,
    )

    print(
        f"Query status: {response.status_code} "
        f"(start={start}, batch={QUERY_BATCH_SIZE})"
    )

    response.raise_for_status()

    data = response.json()
    pages = []

    for entry in data.get("searchResults", []):
        pages.append(
            {
                "page_full_name": entry.get("pageFullName", ""),
                "page_name": entry.get("pageName", ""),
                "space": entry.get("space", SPACE),
            }
        )

    return pages


# ---------------------------------------------------------------------------
# XWiki response normalization
# ---------------------------------------------------------------------------

def normalize_object_summaries(objects_data):
    """
    Normalize object-list responses from different XWiki versions.
    """

    summaries = objects_data.get("objectSummaries")

    if summaries is None:
        summaries = objects_data.get("objectSummary")

    if summaries is None:
        summaries = objects_data.get("objects")

    if summaries is None:
        return []

    if isinstance(summaries, dict):
        nested = summaries.get("objectSummary")

        if nested is not None:
            summaries = nested
        else:
            summaries = [summaries]

    if isinstance(summaries, dict):
        summaries = [summaries]

    if not isinstance(summaries, list):
        return []

    return [
        item
        for item in summaries
        if isinstance(item, dict)
    ]


def normalize_properties(properties_response):
    """
    Normalize a properties response into a list.
    """

    properties = properties_response.get(
        "properties",
        [],
    )

    if isinstance(properties, dict):
        nested = properties.get("property")

        if nested is not None:
            properties = nested
        else:
            properties = [properties]

    if isinstance(properties, dict):
        properties = [properties]

    if not isinstance(properties, list):
        return []

    return [
        item
        for item in properties
        if isinstance(item, dict)
    ]


def normalize_attachment_summaries(attachments_data):
    """
    Normalize attachment-list responses from different XWiki versions.
    """

    summaries = attachments_data.get("attachmentSummaries")

    if summaries is None:
        summaries = attachments_data.get("attachmentSummary")

    if summaries is None:
        summaries = attachments_data.get("attachments")

    if summaries is None:
        return []

    if isinstance(summaries, dict):
        nested = summaries.get("attachmentSummary")

        if nested is not None:
            summaries = nested
        else:
            summaries = [summaries]

    if isinstance(summaries, dict):
        summaries = [summaries]

    if not isinstance(summaries, list):
        return []

    return [
        item
        for item in summaries
        if isinstance(item, dict)
    ]


# ---------------------------------------------------------------------------
# CIL object extraction
# ---------------------------------------------------------------------------

def get_page_metadata(page):
    """
    Retrieve the page metadata and confirm that its REST URL exists.
    """

    page_url = build_page_url(page)

    response = session.get(
        page_url,
        timeout=60,
    )

    if not response.ok:
        raise requests.HTTPError(
            f"{response.status_code} error retrieving page.\n"
            f"Page: {page.get('page_full_name', '')}\n"
            f"pageName: {page.get('page_name', '')!r}\n"
            f"URL: {page_url}\n"
            f"Response: {response.text[:500]}",
            response=response,
        )

    return response.json(), page_url


def get_cil_properties(page, page_metadata, page_url):
    """
    Find the actual CIL object attached to the page and retrieve its
    properties.
    """

    page_full_name = page.get("page_full_name", "")

    objects_url = find_link(
        page_metadata,
        "/objects",
    )

    if not objects_url:
        objects_url = f"{page_url}/objects"

    objects_response = session.get(
        objects_url,
        timeout=60,
    )

    if not objects_response.ok:
        raise requests.HTTPError(
            f"{objects_response.status_code} error retrieving objects.\n"
            f"Page: {page_full_name}\n"
            f"URL: {objects_url}\n"
            f"Response: {objects_response.text[:500]}",
            response=objects_response,
        )

    objects_data = objects_response.json()
    object_summaries = normalize_object_summaries(
        objects_data
    )

    matching_object = None

    for object_summary in object_summaries:
        if object_summary.get("className") == CLASS_NAME:
            matching_object = object_summary
            break

    if matching_object is None:
        hidden = page_metadata.get("hidden", False)
        comment = page_metadata.get("comment", "")
        content = page_metadata.get("content", "")

        details = []

        if hidden:
            details.append("page is hidden")

        if comment:
            details.append(f"comment={comment!r}")

        if not content:
            details.append("page content is empty")

        detail_text = (
            "; ".join(details)
            if details
            else "no matching CIL object was found"
        )

        raise NonCILPageError(
            f"The page has no {CLASS_NAME} object: "
            f"{detail_text}."
        )

    properties_url = find_link(
        matching_object,
        "/properties",
    )

    if not properties_url:
        object_url = find_link(
            matching_object,
            "/object",
        )

        if object_url:
            properties_url = (
                f"{object_url.rstrip('/')}/properties"
            )

    if not properties_url:
        object_number = matching_object.get("number")

        if object_number is None:
            raise ValueError(
                "XWiki found the CIL object but returned "
                f"no object number for {page_full_name}."
            )

        class_encoded = quote(
            CLASS_NAME,
            safe=".",
        )

        properties_url = (
            f"{page_url}/objects/"
            f"{class_encoded}/{object_number}/properties"
        )

    properties_response = session.get(
        properties_url,
        timeout=60,
    )

    if not properties_response.ok:
        raise requests.HTTPError(
            f"{properties_response.status_code} "
            f"error retrieving CIL properties.\n"
            f"Page: {page_full_name}\n"
            f"URL: {properties_url}\n"
            f"Response: {properties_response.text[:500]}",
            response=properties_response,
        )

    return properties_response.json(), properties_url


def extract_field_values(properties_response):
    """
    Convert the CIL properties response into a dictionary.
    """

    properties = normalize_properties(
        properties_response
    )

    values = {}

    for property_item in properties:
        name = property_item.get("name")

        if name:
            values[name] = property_item.get(
                "value",
                "",
            )

    return values


# ---------------------------------------------------------------------------
# Attachment inventory
# ---------------------------------------------------------------------------

def get_attachments(page, page_metadata, page_url):
    """
    Retrieve the attachment summaries for a page.

    This function does not download any files.
    """

    page_full_name = page.get("page_full_name", "")

    attachments_url = find_link(
        page_metadata,
        "/attachments",
    )

    if not attachments_url:
        attachments_url = f"{page_url}/attachments"

    response = session.get(
        attachments_url,
        timeout=60,
    )

    if response.status_code == 404:
        # Some pages with no attachments may return an empty result or 404,
        # depending on the XWiki version.
        return [], attachments_url

    if not response.ok:
        raise requests.HTTPError(
            f"{response.status_code} error retrieving attachments.\n"
            f"Page: {page_full_name}\n"
            f"URL: {attachments_url}\n"
            f"Response: {response.text[:500]}",
            response=response,
        )

    attachments_data = response.json()
    attachment_summaries = normalize_attachment_summaries(
        attachments_data
    )

    return attachment_summaries, attachments_url


def get_attachment_filename(attachment):
    """
    Retrieve a filename using the possible keys returned by XWiki.
    """

    return (
        attachment.get("name")
        or attachment.get("filename")
        or attachment.get("fileName")
        or ""
    )


def get_attachment_download_url(
    attachment,
    page_url,
    filename,
):
    """
    Find or construct the download URL for one attachment.
    """

    possible_relations = [
        "/attachment",
        "/download",
        "/content",
    ]

    for relation in possible_relations:
        url = find_link(
            attachment,
            relation,
        )

        if url:
            return url

    direct_href = attachment.get("href")

    if direct_href:
        return direct_href

    filename_encoded = quote(
        filename,
        safe="",
    )

    return (
        f"{page_url}/attachments/"
        f"{filename_encoded}"
    )


def normalize_reference_text(value):
    """
    Normalize text before looking for an attachment filename.
    """

    if value is None:
        return ""

    text = str(value)
    text = html.unescape(text)
    text = unquote(text)

    return text.casefold()


def find_referencing_fields(filename, field_values):
    """
    Find CIL fields that contain the attachment filename.

    This detects references such as:
        {{pdfviewer file="document.pdf"/}}
        [[document.pdf]]
        attachment:document.pdf
    """

    if not filename:
        return []

    normalized_filename = normalize_reference_text(
        filename
    )

    referenced_fields = []

    for field_name, field_value in field_values.items():
        normalized_value = normalize_reference_text(
            field_value
        )

        if (
            normalized_filename
            and normalized_filename in normalized_value
        ):
            referenced_fields.append(field_name)

    return referenced_fields


def build_attachment_inventory_row(
    page,
    page_url,
    field_values,
    attachment,
):
    """
    Convert one XWiki attachment summary into one inventory row.
    """

    filename = get_attachment_filename(
        attachment
    )

    download_url = get_attachment_download_url(
        attachment,
        page_url,
        filename,
    )

    referenced_fields = find_referencing_fields(
        filename,
        field_values,
    )

    mime_type = (
        attachment.get("mimeType")
        or attachment.get("mediaType")
        or attachment.get("contentType")
        or ""
    )

    size_bytes = safe_integer(
        attachment.get("size")
        or attachment.get("sizeBytes")
    )

    return {
        "xwiki_page": page.get(
            "page_full_name",
            "",
        ),
        "client_name": field_values.get(
            "clientname",
            "",
        ),
        "xwiki_page_name": page.get(
            "page_name",
            "",
        ),
        "xwiki_page_url": page_url,
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "size_mb": round(
            size_bytes / (1024 * 1024),
            3,
        ),
        "version": attachment.get(
            "version",
            "",
        ),
        "author": (
            attachment.get("author")
            or attachment.get("creator")
            or ""
        ),
        "created": attachment.get(
            "created",
            "",
        ),
        "modified": attachment.get(
            "date",
            attachment.get("modified", ""),
        ),
        "xwiki_download_url": download_url,
        "referenced_in_any_field": (
            "yes" if referenced_fields else "no"
        ),
        "referenced_fields": "; ".join(
            referenced_fields
        ),
        "reference_field_count": len(
            referenced_fields
        ),
    }


# ---------------------------------------------------------------------------
# Main inventory
# ---------------------------------------------------------------------------

def main():
    attachment_rows = []
    client_summary_rows = []
    skipped_rows = []
    error_rows = []

    start = 0
    candidate_number = 0
    successful_cil_records = 0

    while successful_cil_records < INVENTORY_LIMIT:
        pages = get_page_batch(start)

        if not pages:
            print(
                "No additional pages were returned by XWiki."
            )
            break

        print(
            f"Received {len(pages)} candidate pages."
        )

        for page in pages:
            if successful_cil_records >= INVENTORY_LIMIT:
                break

            candidate_number += 1

            page_full_name = page.get(
                "page_full_name",
                "",
            )

            print()
            print(
                f"[candidate {candidate_number}] "
                f"[inventoried "
                f"{successful_cil_records}/{INVENTORY_LIMIT}] "
                f"Processing {page_full_name}"
            )

            try:
                page_metadata, page_url = get_page_metadata(
                    page
                )

                (
                    properties_response,
                    properties_url,
                ) = get_cil_properties(
                    page,
                    page_metadata,
                    page_url,
                )

                field_values = extract_field_values(
                    properties_response
                )

                (
                    attachment_summaries,
                    attachments_url,
                ) = get_attachments(
                    page,
                    page_metadata,
                    page_url,
                )

                client_attachment_rows = []

                for attachment in attachment_summaries:
                    attachment_row = (
                        build_attachment_inventory_row(
                            page,
                            page_url,
                            field_values,
                            attachment,
                        )
                    )

                    attachment_rows.append(
                        attachment_row
                    )

                    client_attachment_rows.append(
                        attachment_row
                    )

                attachment_count = len(
                    client_attachment_rows
                )

                total_size_bytes = sum(
                    row["size_bytes"]
                    for row in client_attachment_rows
                )

                referenced_count = sum(
                    1
                    for row in client_attachment_rows
                    if row["referenced_in_any_field"] == "yes"
                )

                unreferenced_count = (
                    attachment_count - referenced_count
                )

                filenames = [
                    row["filename"]
                    for row in client_attachment_rows
                    if row["filename"]
                ]

                mime_types = sorted(
                    {
                        row["mime_type"]
                        for row in client_attachment_rows
                        if row["mime_type"]
                    }
                )

                client_summary_rows.append(
                    {
                        "xwiki_page": page_full_name,
                        "client_name": field_values.get(
                            "clientname",
                            "",
                        ),
                        "xwiki_page_name": page.get(
                            "page_name",
                            "",
                        ),
                        "xwiki_page_url": page_url,
                        "xwiki_properties_url": properties_url,
                        "xwiki_attachments_url": attachments_url,
                        "attachment_count": attachment_count,
                        "total_size_bytes": total_size_bytes,
                        "total_size_mb": round(
                            total_size_bytes
                            / (1024 * 1024),
                            3,
                        ),
                        "referenced_attachment_count": (
                            referenced_count
                        ),
                        "unreferenced_attachment_count": (
                            unreferenced_count
                        ),
                        "has_attachments": (
                            "yes"
                            if attachment_count > 0
                            else "no"
                        ),
                        "filenames": "; ".join(
                            filenames
                        ),
                        "mime_types": "; ".join(
                            mime_types
                        ),
                    }
                )

                successful_cil_records += 1

                print(
                    f"Inventoried successfully "
                    f"({successful_cil_records}/"
                    f"{INVENTORY_LIMIT}); "
                    f"attachments={attachment_count}."
                )

            except NonCILPageError as error:
                try:
                    page_url = build_page_url(
                        page
                    )
                except Exception:
                    page_url = ""

                print(
                    f"Skipping non-CIL page: "
                    f"{page_full_name}"
                )
                print(error)

                skipped_rows.append(
                    {
                        "xwiki_page": page_full_name,
                        "xwiki_page_name": page.get(
                            "page_name",
                            "",
                        ),
                        "xwiki_page_url": page_url,
                        "reason": str(error),
                    }
                )

            except Exception as error:
                try:
                    page_url = build_page_url(
                        page
                    )
                except Exception:
                    page_url = ""

                print(
                    f"Inventory error: "
                    f"{page_full_name}"
                )
                print(error)

                error_rows.append(
                    {
                        "xwiki_page": page_full_name,
                        "xwiki_page_name": page.get(
                            "page_name",
                            "",
                        ),
                        "xwiki_page_url": page_url,
                        "error": str(error),
                    }
                )

        start += len(pages)

        if len(pages) < QUERY_BATCH_SIZE:
            print(
                "XWiki returned fewer pages than the "
                "batch size. There may be no more pages."
            )
            break

    attachment_fieldnames = [
        "xwiki_page",
        "client_name",
        "xwiki_page_name",
        "xwiki_page_url",
        "filename",
        "mime_type",
        "size_bytes",
        "size_mb",
        "version",
        "author",
        "created",
        "modified",
        "xwiki_download_url",
        "referenced_in_any_field",
        "referenced_fields",
        "reference_field_count",
    ]

    summary_fieldnames = [
        "xwiki_page",
        "client_name",
        "xwiki_page_name",
        "xwiki_page_url",
        "xwiki_properties_url",
        "xwiki_attachments_url",
        "attachment_count",
        "total_size_bytes",
        "total_size_mb",
        "referenced_attachment_count",
        "unreferenced_attachment_count",
        "has_attachments",
        "filenames",
        "mime_types",
    ]

    skipped_fieldnames = [
        "xwiki_page",
        "xwiki_page_name",
        "xwiki_page_url",
        "reason",
    ]

    error_fieldnames = [
        "xwiki_page",
        "xwiki_page_name",
        "xwiki_page_url",
        "error",
    ]

    write_csv(
        ATTACHMENT_INVENTORY_FILE,
        attachment_fieldnames,
        attachment_rows,
    )

    write_csv(
        CLIENT_SUMMARY_FILE,
        summary_fieldnames,
        client_summary_rows,
    )

    write_csv(
        SKIPPED_FILE,
        skipped_fieldnames,
        skipped_rows,
    )

    write_csv(
        ERROR_FILE,
        error_fieldnames,
        error_rows,
    )

    clients_with_attachments = sum(
        1
        for row in client_summary_rows
        if row["attachment_count"] > 0
    )

    clients_without_attachments = (
        len(client_summary_rows)
        - clients_with_attachments
    )

    total_attachment_size = sum(
        row["size_bytes"]
        for row in attachment_rows
    )

    unreferenced_attachments = sum(
        1
        for row in attachment_rows
        if row["referenced_in_any_field"] == "no"
    )

    print()
    print("=" * 72)
    print("Attachment inventory completed")
    print("=" * 72)
    print(
        f"Successful CIL records: "
        f"{successful_cil_records}"
    )
    print(
        f"Clients with attachments: "
        f"{clients_with_attachments}"
    )
    print(
        f"Clients without attachments: "
        f"{clients_without_attachments}"
    )
    print(
        f"Total attachments found: "
        f"{len(attachment_rows)}"
    )
    print(
        f"Total attachment size: "
        f"{round(total_attachment_size / (1024 * 1024), 2)} MB"
    )
    print(
        f"Unreferenced attachments: "
        f"{unreferenced_attachments}"
    )
    print(
        f"Skipped non-CIL pages: "
        f"{len(skipped_rows)}"
    )
    print(
        f"Unexpected errors: "
        f"{len(error_rows)}"
    )
    print()
    print(
        f"Attachment inventory: "
        f"{ATTACHMENT_INVENTORY_FILE}"
    )
    print(
        f"Client summary: "
        f"{CLIENT_SUMMARY_FILE}"
    )
    print(
        f"Skipped pages: "
        f"{SKIPPED_FILE}"
    )
    print(
        f"Errors: "
        f"{ERROR_FILE}"
    )


if __name__ == "__main__":
    main()