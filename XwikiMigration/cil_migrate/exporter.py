from __future__ import annotations

from .config import settings
from .csv_utils import write_csv
from .fields import FIELDS
from .logging_utils import configure_logging
from .xwiki import NonCILPageError, XWikiClient


def export_clients(limit: int, batch_size: int = 100) -> None:
    logger = configure_logging(settings.logs_dir / "migration.log")
    client = XWikiClient()

    rows = []
    skipped = []
    errors = []
    start = 0

    while len(rows) < limit:
        pages = client.get_page_batch(start, batch_size)

        if not pages:
            break

        for page in pages:
            if len(rows) >= limit:
                break

            logger.info("Exporting %s", page.page_full_name)

            try:
                metadata, page_url = client.get_page_metadata(page)
                properties, properties_url = client.get_cil_properties(
                    page,
                    metadata,
                    page_url,
                )
                values = client.extract_values(properties)

                row = {
                    "xwiki_page": page.page_full_name,
                    "xwiki_page_name": page.page_name,
                    "xwiki_page_url": page_url,
                    "xwiki_properties_url": properties_url,
                }
                row.update({field: values.get(field, "") for field in FIELDS})
                rows.append(row)

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

    output = settings.clients_dir / f"cil_clients_{len(rows)}.csv"
    write_csv(
        output,
        [
            "xwiki_page",
            "xwiki_page_name",
            "xwiki_page_url",
            "xwiki_properties_url",
        ]
        + FIELDS,
        rows,
    )
    write_csv(
        settings.logs_dir / "client_export_skipped.csv",
        ["xwiki_page", "reason"],
        skipped,
    )
    write_csv(
        settings.logs_dir / "client_export_errors.csv",
        ["xwiki_page", "error"],
        errors,
    )

    logger.info("Exported %s records to %s", len(rows), output)
