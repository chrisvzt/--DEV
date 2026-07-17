from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from config import settings
from xwiki_api import NonCILPageError, XWikiClient


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict],
) -> None:
    with path.open(
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
    )
    args = parser.parse_args()

    client = XWikiClient()
    attachment_rows: list[dict] = []
    summary_rows: list[dict] = []
    skipped_rows: list[dict] = []
    error_rows: list[dict] = []

    successful = 0
    start = 0

    while successful < args.limit:
        pages = client.get_page_batch(
            start,
            args.batch_size,
        )

        if not pages:
            break

        for page in pages:
            if successful >= args.limit:
                break

            full_name = page["page_full_name"]
            print(
                f"[{successful}/{args.limit}] "
                f"{full_name}"
            )

            try:
                metadata, page_url = (
                    client.get_page_metadata(page)
                )
                properties, properties_url = (
                    client.get_cil_properties(
                        page,
                        metadata,
                        page_url,
                    )
                )
                values = client.extract_field_values(
                    properties
                )
                attachments, attachments_url = (
                    client.get_attachments(
                        page,
                        metadata,
                        page_url,
                    )
                )

                per_client: list[dict] = []

                for attachment in attachments:
                    filename = (
                        client.get_attachment_filename(
                            attachment
                        )
                    )
                    size = safe_int(
                        attachment.get("size")
                        or attachment.get("sizeBytes")
                    )
                    mime_type = (
                        attachment.get("mimeType")
                        or attachment.get("mediaType")
                        or attachment.get("contentType")
                        or ""
                    )
                    download_url = (
                        client.get_attachment_download_url(
                            attachment,
                            page_url,
                            filename,
                        )
                    )
                    referenced_fields = (
                        client.find_referencing_fields(
                            filename,
                            values,
                        )
                    )

                    row = {
                        "xwiki_page": full_name,
                        "client_name": values.get(
                            "clientname",
                            "",
                        ),
                        "xwiki_page_name": page["page_name"],
                        "xwiki_page_url": page_url,
                        "filename": filename,
                        "mime_type": mime_type,
                        "size_bytes": size,
                        "size_mb": round(
                            size / (1024 * 1024),
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
                        "modified": (
                            attachment.get("date")
                            or attachment.get("modified")
                            or ""
                        ),
                        "xwiki_download_url": download_url,
                        "referenced_in_any_field": (
                            "yes"
                            if referenced_fields
                            else "no"
                        ),
                        "referenced_fields": "; ".join(
                            referenced_fields
                        ),
                        "reference_field_count": len(
                            referenced_fields
                        ),
                    }
                    attachment_rows.append(row)
                    per_client.append(row)

                total_size = sum(
                    row["size_bytes"]
                    for row in per_client
                )
                referenced_count = sum(
                    1
                    for row in per_client
                    if row["referenced_in_any_field"]
                    == "yes"
                )

                summary_rows.append(
                    {
                        "xwiki_page": full_name,
                        "client_name": values.get(
                            "clientname",
                            "",
                        ),
                        "xwiki_page_name": page["page_name"],
                        "xwiki_page_url": page_url,
                        "xwiki_properties_url": properties_url,
                        "xwiki_attachments_url": attachments_url,
                        "attachment_count": len(per_client),
                        "total_size_bytes": total_size,
                        "total_size_mb": round(
                            total_size / (1024 * 1024),
                            3,
                        ),
                        "referenced_attachment_count": referenced_count,
                        "unreferenced_attachment_count": (
                            len(per_client)
                            - referenced_count
                        ),
                        "has_attachments": (
                            "yes" if per_client else "no"
                        ),
                        "filenames": "; ".join(
                            row["filename"]
                            for row in per_client
                        ),
                        "mime_types": "; ".join(
                            sorted(
                                {
                                    row["mime_type"]
                                    for row in per_client
                                    if row["mime_type"]
                                }
                            )
                        ),
                    }
                )
                successful += 1

            except NonCILPageError as exc:
                skipped_rows.append(
                    {
                        "xwiki_page": full_name,
                        "reason": str(exc),
                    }
                )
            except Exception as exc:
                error_rows.append(
                    {
                        "xwiki_page": full_name,
                        "error": str(exc),
                    }
                )

        start += len(pages)

        if len(pages) < args.batch_size:
            break

    write_csv(
        settings.inventory_dir
        / "cil_attachment_inventory.csv",
        [
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
        ],
        attachment_rows,
    )

    write_csv(
        settings.inventory_dir
        / "cil_client_attachment_summary.csv",
        [
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
        ],
        summary_rows,
    )

    write_csv(
        settings.logs_dir
        / "inventory_skipped_pages.csv",
        ["xwiki_page", "reason"],
        skipped_rows,
    )
    write_csv(
        settings.logs_dir
        / "inventory_errors.csv",
        ["xwiki_page", "error"],
        error_rows,
    )

    print(
        f"Inventoried {successful} clients and "
        f"{len(attachment_rows)} attachments."
    )


if __name__ == "__main__":
    main()
