from __future__ import annotations

from collections import Counter
from pathlib import Path

from .config import settings
from .csv_utils import read_csv


def create_report() -> None:
    inventory = read_csv(
        settings.inventory_dir / "cil_attachment_inventory.csv"
    )
    summary = read_csv(
        settings.inventory_dir / "cil_client_attachment_summary.csv"
    )

    mime_counts = Counter(
        row.get("mime_type", "") or "(blank)"
        for row in inventory
    )
    extension_counts = Counter(
        Path(row.get("filename", "")).suffix.lower() or "(none)"
        for row in inventory
    )

    with (settings.logs_dir / "inventory_report.txt").open(
        "w",
        encoding="utf-8",
    ) as output:
        output.write(f"Clients: {len(summary)}\n")
        output.write(f"Attachments: {len(inventory)}\n\n")

        output.write("MIME types\n")
        output.write("-" * 50 + "\n")
        for name, count in mime_counts.most_common():
            output.write(f"{count:6}  {name}\n")

        output.write("\nExtensions\n")
        output.write("-" * 50 + "\n")
        for name, count in extension_counts.most_common():
            output.write(f"{count:6}  {name}\n")
