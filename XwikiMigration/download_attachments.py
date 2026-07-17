from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path

from config import settings
from xwiki_api import XWikiClient


INVALID_FILENAME_CHARS = re.compile(
    r'[<>:"/\\|?*\x00-\x1F]'
)


def safe_component(value: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub(
        "_",
        value.strip(),
    )
    cleaned = cleaned.rstrip(". ")
    return cleaned[:180] or "_unnamed"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inventory",
        default=str(
            settings.inventory_dir
            / "cil_attachment_inventory.csv"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="0 means download every inventory row.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
    )
    args = parser.parse_args()

    client = XWikiClient()
    inventory_path = Path(args.inventory)

    with inventory_path.open(
        encoding="utf-8-sig",
        newline="",
    ) as source:
        rows = list(csv.DictReader(source))

    if args.limit > 0:
        rows = rows[:args.limit]

    results: list[dict] = []

    for index, row in enumerate(rows, start=1):
        page_name = (
            row.get("client_name")
            or row.get("xwiki_page_name")
            or row.get("xwiki_page")
            or "_unknown"
        )
        filename = row.get("filename", "")
        url = row.get("xwiki_download_url", "")

        client_folder = (
            settings.attachments_dir
            / safe_component(page_name)
        )
        destination = (
            client_folder
            / safe_component(filename)
        )

        status = ""
        error = ""
        downloaded_size = 0
        checksum = ""

        try:
            if (
                destination.exists()
                and not args.overwrite
            ):
                status = "already_exists"
                downloaded_size = (
                    destination.stat().st_size
                )
            else:
                downloaded_size = client.download(
                    url,
                    destination,
                )
                status = "downloaded"

            checksum = sha256_file(destination)

        except Exception as exc:
            status = "error"
            error = str(exc)

        result = dict(row)
        result.update(
            {
                "local_path": str(
                    destination.relative_to(
                        settings.project_root
                    )
                ),
                "download_status": status,
                "downloaded_size_bytes": (
                    downloaded_size
                ),
                "sha256": checksum,
                "download_error": error,
            }
        )
        results.append(result)

        print(
            f"[{index}/{len(rows)}] "
            f"{status}: {page_name} / {filename}"
        )

    output = (
        settings.inventory_dir
        / "cil_attachment_download_results.csv"
    )

    fieldnames = list(results[0].keys()) if results else [
        "xwiki_page",
        "filename",
        "download_status",
        "download_error",
    ]

    with output.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"Download results written to {output}")


if __name__ == "__main__":
    main()
