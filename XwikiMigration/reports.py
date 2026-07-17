from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from config import settings


def read_csv(path: Path) -> list[dict]:
    with path.open(
        encoding="utf-8-sig",
        newline="",
    ) as source:
        return list(csv.DictReader(source))


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
        "--summary",
        default=str(
            settings.inventory_dir
            / "cil_client_attachment_summary.csv"
        ),
    )
    args = parser.parse_args()

    inventory = read_csv(Path(args.inventory))
    summary = read_csv(Path(args.summary))

    mime_counts = Counter(
        row.get("mime_type", "") or "(blank)"
        for row in inventory
    )
    extension_counts = Counter(
        Path(row.get("filename", "")).suffix.lower()
        or "(none)"
        for row in inventory
    )

    clients_with = sum(
        1 for row in summary
        if row.get("has_attachments") == "yes"
    )
    clients_without = len(summary) - clients_with

    largest = sorted(
        summary,
        key=lambda row: float(
            row.get("total_size_mb") or 0
        ),
        reverse=True,
    )[:20]

    most_attachments = sorted(
        summary,
        key=lambda row: int(
            row.get("attachment_count") or 0
        ),
        reverse=True,
    )[:20]

    report_path = (
        settings.logs_dir
        / "inventory_report.txt"
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as output:
        output.write(
            f"Clients inventoried: {len(summary)}\n"
        )
        output.write(
            f"Clients with attachments: {clients_with}\n"
        )
        output.write(
            f"Clients without attachments: {clients_without}\n"
        )
        output.write(
            f"Attachments: {len(inventory)}\n\n"
        )

        output.write("MIME types\n")
        output.write("-" * 60 + "\n")
        for name, count in mime_counts.most_common():
            output.write(f"{count:6}  {name}\n")

        output.write("\nExtensions\n")
        output.write("-" * 60 + "\n")
        for name, count in extension_counts.most_common():
            output.write(f"{count:6}  {name}\n")

        output.write("\nTop clients by total size\n")
        output.write("-" * 60 + "\n")
        for row in largest:
            output.write(
                f"{row.get('total_size_mb', '0'):>10} MB  "
                f"{row.get('client_name') or row.get('xwiki_page')}\n"
            )

        output.write("\nTop clients by attachment count\n")
        output.write("-" * 60 + "\n")
        for row in most_attachments:
            output.write(
                f"{row.get('attachment_count', '0'):>6}  "
                f"{row.get('client_name') or row.get('xwiki_page')}\n"
            )

    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
