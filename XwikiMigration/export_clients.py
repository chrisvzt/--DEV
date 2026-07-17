from __future__ import annotations

import argparse
import csv
from pathlib import Path

from config import settings
from xwiki_api import NonCILPageError, XWikiClient


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
        default=50,
        help="Number of successful CIL records to export.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
    )
    args = parser.parse_args()

    client = XWikiClient()
    exported: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []

    start = 0

    while len(exported) < args.limit:
        pages = client.get_page_batch(
            start,
            args.batch_size,
        )

        if not pages:
            break

        for page in pages:
            if len(exported) >= args.limit:
                break

            full_name = page["page_full_name"]
            print(
                f"[{len(exported)}/{args.limit}] "
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

                row = {
                    "xwiki_page": full_name,
                    "xwiki_page_name": page["page_name"],
                    "xwiki_page_url": page_url,
                    "xwiki_properties_url": properties_url,
                }
                for field in FIELDS:
                    row[field] = values.get(
                        field,
                        "",
                    )

                exported.append(row)

            except NonCILPageError as exc:
                skipped.append(
                    {
                        "xwiki_page": full_name,
                        "reason": str(exc),
                    }
                )
            except Exception as exc:
                errors.append(
                    {
                        "xwiki_page": full_name,
                        "error": str(exc),
                    }
                )

        start += len(pages)

        if len(pages) < args.batch_size:
            break

    output = (
        settings.clients_dir
        / f"cil_clients_{len(exported)}.csv"
    )

    write_csv(
        output,
        [
            "xwiki_page",
            "xwiki_page_name",
            "xwiki_page_url",
            "xwiki_properties_url",
        ] + FIELDS,
        exported,
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

    print(f"Exported {len(exported)} records to {output}")


if __name__ == "__main__":
    main()
