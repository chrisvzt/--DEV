from __future__ import annotations

import argparse

from .config import settings
from .downloader import download_attachments
from .exporter import export_clients
from .inventory import inventory_attachments
from .reporting import create_report
from .xwiki import XWikiClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description="XWiki CIL Migration Toolkit"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export_parser = sub.add_parser("export-clients")
    export_parser.add_argument("--limit", type=int, default=50)
    export_parser.add_argument("--batch-size", type=int, default=100)

    inventory_parser = sub.add_parser("inventory")
    inventory_parser.add_argument("--limit", type=int, default=500)
    inventory_parser.add_argument("--batch-size", type=int, default=100)

    download_parser = sub.add_parser("download")
    download_parser.add_argument("--limit", type=int, default=0)
    download_parser.add_argument("--overwrite", action="store_true")

    sub.add_parser("report")
    sub.add_parser("validate")

    args = parser.parse_args()

    if args.command == "export-clients":
        export_clients(args.limit, args.batch_size)
    elif args.command == "inventory":
        inventory_attachments(args.limit, args.batch_size)
    elif args.command == "download":
        download_attachments(args.limit, args.overwrite)
    elif args.command == "report":
        create_report()
    elif args.command == "validate":
        settings.validate_xwiki()
        client = XWikiClient()
        pages = client.get_page_batch(0, 1)
        print("Configuration valid.")
        print(f"XWiki returned {len(pages)} test page(s).")
