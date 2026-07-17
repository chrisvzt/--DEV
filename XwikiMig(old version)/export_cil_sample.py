import csv
import os
from urllib.parse import quote

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

# Set the password in PowerShell before running the script:
#
# $env:XWIKI_PASSWORD = "your-password"
#
PASSWORD = os.environ.get("XWIKI_PASSWORD")

CLASS_NAME = "ClientInfoLibraryCode.ClientInfoLibraryClass"
SPACE = "Client Info Library"

# Export exactly this many successful CIL records.
EXPORT_LIMIT = 50

# Number of candidate pages requested from XWiki at a time.
QUERY_BATCH_SIZE = 100

OUTPUT_FILE = "cil_sample_50.csv"
ERROR_FILE = "cil_export_errors.csv"
SKIPPED_FILE = "cil_skipped_non_cil_pages.csv"


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
        "Then run the script again."
    )


session = requests.Session()

# Temporary workaround for the internal XWiki SSL certificate.
# For the final migration, replace False with the path to your company CA file.
session.verify = False

session.auth = HTTPBasicAuth(USERNAME, PASSWORD)

session.headers.update(
    {
        "Accept": "application/json",
    }
)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def build_page_url(page):
    """
    Build the REST URL for a page using the exact pageName and space values
    returned by XWiki.
    """

    space = page.get("space", SPACE)
    page_name = page.get("page_name", "")

    if not page_name:
        raise ValueError(
            f"XWiki returned no pageName for "
            f"{page.get('page_full_name', '(unknown page)')!r}."
        )

    space_encoded = quote(space, safe="")
    page_encoded = quote(page_name, safe="")

    return (
        f"{XWIKI_BASE_URL}/rest/wikis/{XWIKI_WIKI_NAME}/"
        f"spaces/{space_encoded}/pages/{page_encoded}"
    )


def find_link(item, relation_suffix):
    """
    Find an XWiki REST link whose rel attribute ends with relation_suffix.

    Examples:
        /object
        /properties
        /objects
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


# ---------------------------------------------------------------------------
# Query pages
# ---------------------------------------------------------------------------

def get_page_batch(start):
    """
    Retrieve one batch of visible pages from the Client Info Library space.

    Hidden redirect pages are excluded by the query when supported by this
    XWiki version. Pages are still checked for a real CIL object afterward.
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
# Page and object inspection
# ---------------------------------------------------------------------------

def normalize_object_summaries(objects_data):
    """
    Normalize the different JSON structures returned by XWiki versions.

    Depending on the version, the response may use:
        objectSummaries
        objectSummary
        objects
    """

    summaries = objects_data.get("objectSummaries")

    if summaries is None:
        summaries = objects_data.get("objectSummary")

    if summaries is None:
        summaries = objects_data.get("objects")

    if summaries is None:
        return []

    if isinstance(summaries, dict):
        # Some responses wrap the list one level deeper.
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


def get_page_metadata(page):
    """
    Retrieve the page itself. This confirms that its REST URL exists and lets
    us identify redirects or hidden utility pages when needed.
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


def get_cil_properties(page):
    """
    Inspect all objects attached to a page, find the actual
    ClientInfoLibraryClass object, and retrieve its properties.

    This does not assume that the object number is always 0.
    """

    page_full_name = page.get("page_full_name", "")
    page_metadata, page_url = get_page_metadata(page)

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
            f"{objects_response.status_code} error retrieving page objects.\n"
            f"Page: {page_full_name}\n"
            f"URL: {objects_url}\n"
            f"Response: {objects_response.text[:500]}",
            response=objects_response,
        )

    objects_data = objects_response.json()
    object_summaries = normalize_object_summaries(objects_data)

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
            f"The page has no {CLASS_NAME} object: {detail_text}."
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
            properties_url = f"{object_url.rstrip('/')}/properties"

    if not properties_url:
        object_number = matching_object.get("number")

        if object_number is None:
            raise ValueError(
                f"XWiki found the CIL object but returned no object number.\n"
                f"Page: {page_full_name}"
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

    print(
        "Properties status:",
        properties_response.status_code,
        page_full_name,
    )

    if not properties_response.ok:
        raise requests.HTTPError(
            f"{properties_response.status_code} "
            f"error retrieving properties.\n"
            f"Page: {page_full_name}\n"
            f"URL: {properties_url}\n"
            f"Response: {properties_response.text[:500]}",
            response=properties_response,
        )

    return (
        properties_response.json(),
        page_url,
        properties_url,
    )


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_properties(properties_response):
    """
    Convert an XWiki properties response into one CSV row.
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
        properties = []

    values = {}

    for property_item in properties:
        if not isinstance(property_item, dict):
            continue

        name = property_item.get("name")

        if name:
            values[name] = property_item.get(
                "value",
                "",
            )

    row = {}

    for field in FIELDS:
        row[field] = values.get(
            field,
            "",
        )

    return row


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_csv(filename, fieldnames, rows):
    """
    Write rows to a UTF-8 CSV that opens cleanly in Excel.
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


def write_results(exported_rows, errors, skipped):
    export_fieldnames = [
        "xwiki_page",
        "xwiki_page_name",
        "xwiki_page_url",
        "xwiki_properties_url",
    ] + FIELDS

    error_fieldnames = [
        "xwiki_page",
        "xwiki_page_name",
        "xwiki_page_url",
        "error",
    ]

    skipped_fieldnames = [
        "xwiki_page",
        "xwiki_page_name",
        "xwiki_page_url",
        "reason",
    ]

    write_csv(
        OUTPUT_FILE,
        export_fieldnames,
        exported_rows,
    )

    write_csv(
        ERROR_FILE,
        error_fieldnames,
        errors,
    )

    write_csv(
        SKIPPED_FILE,
        skipped_fieldnames,
        skipped,
    )


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class NonCILPageError(Exception):
    """
    Raised when a page exists but is not an actual CIL data record.
    """


# ---------------------------------------------------------------------------
# Main export
# ---------------------------------------------------------------------------

def main():
    exported_rows = []
    errors = []
    skipped = []

    start = 0
    candidate_number = 0

    while len(exported_rows) < EXPORT_LIMIT:
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
            if len(exported_rows) >= EXPORT_LIMIT:
                break

            candidate_number += 1
            page_full_name = page.get(
                "page_full_name",
                "",
            )

            print()
            print(
                f"[candidate {candidate_number}] "
                f"[exported {len(exported_rows)}/{EXPORT_LIMIT}] "
                f"Processing {page_full_name}"
            )

            try:
                (
                    properties_response,
                    page_url,
                    properties_url,
                ) = get_cil_properties(page)

                row = extract_properties(
                    properties_response
                )

                row["xwiki_page"] = page_full_name
                row["xwiki_page_name"] = page.get(
                    "page_name",
                    "",
                )
                row["xwiki_page_url"] = page_url
                row["xwiki_properties_url"] = properties_url

                exported_rows.append(row)

                print(
                    f"Exported successfully "
                    f"({len(exported_rows)}/{EXPORT_LIMIT})."
                )

            except NonCILPageError as error:
                try:
                    page_url = build_page_url(page)
                except Exception:
                    page_url = ""

                print(
                    f"Skipping non-CIL page: {page_full_name}"
                )
                print(error)

                skipped.append(
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
                    page_url = build_page_url(page)
                except Exception:
                    page_url = ""

                print(
                    f"Error exporting: {page_full_name}"
                )
                print(error)

                errors.append(
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
                "XWiki returned fewer pages than the batch size, "
                "so there may be no more candidates."
            )
            break

    write_results(
        exported_rows,
        errors,
        skipped,
    )

    print()
    print("=" * 70)
    print("Export completed")
    print("=" * 70)
    print(
        f"Successfully exported: {len(exported_rows)}"
    )
    print(
        f"Skipped non-CIL pages: {len(skipped)}"
    )
    print(
        f"Unexpected errors: {len(errors)}"
    )
    print()
    print(f"Data file: {OUTPUT_FILE}")
    print(f"Skipped-pages file: {SKIPPED_FILE}")
    print(f"Errors file: {ERROR_FILE}")

    if len(exported_rows) < EXPORT_LIMIT:
        print()
        print(
            f"Warning: only {len(exported_rows)} of the requested "
            f"{EXPORT_LIMIT} CIL records were exported."
        )


if __name__ == "__main__":
    main()