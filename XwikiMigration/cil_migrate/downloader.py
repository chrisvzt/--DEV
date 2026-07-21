from __future__ import annotations

import hashlib
import re
from pathlib import Path

from tqdm import tqdm

from .config import settings
from .csv_utils import read_csv, write_csv
from .logging_utils import configure_logging
from .xwiki import XWikiClient


INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


def safe_name(value: str) -> str:
    cleaned = INVALID_CHARS.sub("_", value.strip()).rstrip(". ")
    return cleaned[:180] or "_unnamed"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_attachments(limit: int = 0, overwrite: bool = False) -> None:
    logger = configure_logging(settings.logs_dir / "migration.log")
    client = XWikiClient()

    inventory_path = (
        settings.inventory_dir / "cil_attachment_inventory.csv"
    )
    rows = read_csv(inventory_path)

    if limit > 0:
        rows = rows[:limit]

    results = []

    for row in tqdm(rows, desc="Downloading"):
        client_name = (
            row.get("client_name")
            or row.get("xwiki_page_name")
            or "_unknown"
        )
        filename = row.get("filename", "")
        url = row.get("xwiki_download_url", "")

        destination = (
            settings.attachments_dir
            / safe_name(client_name)
            / safe_name(filename)
        )

        status = ""
        error = ""
        size = 0
        checksum = ""

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)

            if destination.exists() and not overwrite:
                status = "already_exists"
            else:
                response = client.session.get(
                    url,
                    stream=True,
                    timeout=180,
                    headers={"Accept": "*/*"},
                )
                response.raise_for_status()

                with destination.open("wb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            output.write(chunk)

                status = "downloaded"

            size = destination.stat().st_size
            checksum = sha256(destination)

        except Exception as exc:
            status = "error"
            error = str(exc)
            logger.error(
                "Download failed: %s / %s: %s",
                client_name,
                filename,
                exc,
            )

        result = dict(row)
        result.update(
            {
                "local_path": str(
                    destination.relative_to(settings.root)
                ),
                "download_status": status,
                "downloaded_size_bytes": size,
                "sha256": checksum,
                "download_error": error,
            }
        )
        results.append(result)

    fieldnames = list(results[0].keys()) if results else [
        "xwiki_page",
        "filename",
        "download_status",
        "download_error",
    ]

    write_csv(
        settings.inventory_dir / "cil_attachment_download_results.csv",
        fieldnames,
        results,
    )
