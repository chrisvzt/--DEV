from __future__ import annotations

from .config import settings
from .csv_utils import write_csv
from .logging_utils import configure_logging
from .xwiki import NonCILPageError, XWikiClient


def safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def inventory_attachments(limit: int, batch_size: int = 100) -> None:
    logger = configure_logging(settings.logs_dir / "migration.log")
    client = XWikiClient()

    attachments = []
    summaries = []
    skipped = []
    errors = []
    successful = 0
    start = 0

    while successful < limit:
        pages = client.get_page_batch(start, batch_size)

        if not pages:
            break

        for page in pages:
            if successful >= limit:
                break

            logger.info("Inventorying %s", page.page_full_name)

            try:
                metadata, page_url = client.get_page_metadata(page)
                properties, properties_url = client.get_cil_properties(
                    page,
                    metadata,
                    page_url,
                )
                values = client.extract_values(properties)
                found, attachments_url = client.get_attachments(
                    metadata,
                    page_url,
                )

                client_rows = []

                for attachment in found:
                    filename = client.attachment_filename(attachment)
                    size = safe_int(
                        attachment.get("size")
                        or attachment.get("sizeBytes")
                    )
                    mime = (
                        attachment.get("mimeType")
                        or attachment.get("mediaType")
                        or attachment.get("contentType")
                        or ""
                    )
                    refs = client.referencing_fields(filename, values)
                    download_url = client.attachment_download_url(
                        attachment,
                        page_url,
                        filename,
                    )

                    row = {
                        "xwiki_page": page.page_full_name,
                        "client_name": values.get("clientname", ""),
                        "xwiki_page_name": page.page_name,
                        "xwiki_page_url": page_url,
                        "filename": filename,
                        "mime_type": mime,
                        "size_bytes": size,
                        "size_mb": round(size / (1024 * 1024), 3),
                        "xwiki_download_url": download_url,
                        "referenced_in_any_field": "yes" if refs else "no",
                        "referenced_fields": "; ".join(refs),
                        "reference_field_count": len(refs),
                    }
                    attachments.append(row)
                    client_rows.append(row)

                total_size = sum(row["size_bytes"] for row in client_rows)
                referenced = sum(
                    row["referenced_in_any_field"] == "yes"
                    for row in client_rows
                )

                summaries.append(
                    {
                        "xwiki_page": page.page_full_name,
                        "client_name": values.get("clientname", ""),
                        "xwiki_page_name": page.page_name,
                        "xwiki_page_url": page_url,
                        "xwiki_properties_url": properties_url,
                        "xwiki_attachments_url": attachments_url,
                        "attachment_count": len(client_rows),
                        "total_size_bytes": total_size,
                        "total_size_mb": round(
                            total_size / (1024 * 1024),
                            3,
                        ),
                        "referenced_attachment_count": referenced,
                        "unreferenced_attachment_count": (
                            len(client_rows) - referenced
                        ),
                        "has_attachments": "yes" if client_rows else "no",
                        "filenames": "; ".join(
                            row["filename"] for row in client_rows
                        ),
                        "mime_types": "; ".join(
                            sorted(
                                {
                                    row["mime_type"]
                                    for row in client_rows
                                    if row["mime_type"]
                                }
                            )
                        ),
                    }
                )

                successful += 1

            except NonCILPageError as exc:
                skipped.append(
                    {"xwiki_page": page.page_full_name, "reason": str(exc)}
                )
            except Exception as exc:
                errors.append(
                    {"xwiki_page": page.page_full_name, "error": str(exc)}
                )

        start += len(pages)
        if len(pages) < batch_size:
            break

    write_csv(
        settings.inventory_dir / "cil_attachment_inventory.csv",
        [
            "xwiki_page",
            "client_name",
            "xwiki_page_name",
            "xwiki_page_url",
            "filename",
            "mime_type",
            "size_bytes",
            "size_mb",
            "xwiki_download_url",
            "referenced_in_any_field",
            "referenced_fields",
            "reference_field_count",
        ],
        attachments,
    )
    write_csv(
        settings.inventory_dir / "cil_client_attachment_summary.csv",
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
        summaries,
    )
    write_csv(
        settings.logs_dir / "inventory_skipped.csv",
        ["xwiki_page", "reason"],
        skipped,
    )
    write_csv(
        settings.logs_dir / "inventory_errors.csv",
        ["xwiki_page", "error"],
        errors,
    )

    logger.info(
        "Inventoried %s clients and %s attachments",
        successful,
        len(attachments),
    )
