from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from config import settings


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_storage_body(row: dict[str, str]) -> str:
    sections = [
        (
            "Account",
            [
                ("Business System", "Business_System"),
                ("Client Name", "clientname"),
                ("Parent Company", "parentcompany"),
                ("Child Company", "childcompany"),
                ("Lead", "lead"),
                ("PM Lead", "pmlead"),
                ("Notes / Known Issues", "notesissues"),
            ],
        ),
        (
            "Intake",
            [
                ("Intake", "intake"),
                ("CID", "cid"),
                ("Legal Entity", "legalentity"),
                ("Requires Quote", "requirequote"),
                ("Quote Approver", "whoapprovequote"),
                ("Refusing Projects", "refusingprojects"),
                ("Submission Rules", "followrules"),
                ("Additional Intake", "intakeinfo"),
            ],
        ),
        (
            "Processing",
            [
                ("Processing Requirements", "processingrequirements"),
                ("Security Requirements", "securityrequirements"),
                ("Translation Memory", "translationmemory"),
                ("Translation Glossary", "translationglossary"),
                ("US Requirements", "usrequirements"),
                ("Delivery Requirements", "deliveryrequirements"),
                ("Certification Needed", "certificationneeded"),
                ("Preferred Linguist", "preferredlinguist"),
                ("Additional Processing", "processinginformation"),
            ],
        ),
        (
            "Pricing and Billing",
            [
                ("Pricing Requirements", "pricingrequirements"),
                ("Pricing Structure", "pricingstructure"),
                ("Contract Details", "expandoncontract"),
                ("Rush Fees", "rushfees"),
                ("Minimums", "minimums"),
                ("Off-contract Languages", "languagenotincluded"),
                ("Billing Method", "billclient"),
                ("PO Requirements", "porequirements"),
                ("Billing Contact", "billingcontact"),
                ("Additional Billing", "billinginfo"),
            ],
        ),
    ]

    chunks = []

    for section_title, fields in sections:
        chunks.append(f"<h2>{html_escape(section_title)}</h2>")
        chunks.append("<table><tbody>")

        for label, key in fields:
            value = row.get(key, "")
            if not value:
                continue
            chunks.append(
                "<tr>"
                f"<th>{html_escape(label)}</th>"
                f"<td><pre>{html_escape(value)}</pre></td>"
                "</tr>"
            )

        chunks.append("</tbody></table>")

    chunks.append(
        "<p><em>Source: "
        f"{html_escape(row.get('xwiki_page_url', ''))}"
        "</em></p>"
    )

    return "".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clients", required=True)
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
    )
    args = parser.parse_args()

    settings.validate_atlassian()

    with Path(args.clients).open(
        encoding="utf-8-sig",
        newline="",
    ) as source:
        rows = list(csv.DictReader(source))

    session = requests.Session()
    session.auth = HTTPBasicAuth(
        settings.atlassian_email,
        settings.atlassian_api_token,
    )
    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )

    for row in rows[: args.limit]:
        title = (
            row.get("clientname")
            or row.get("xwiki_page_name")
            or "Untitled Client"
        )
        payload = {
            "type": "page",
            "title": title,
            "space": {
                "key": settings.confluence_space_key
            },
            "body": {
                "storage": {
                    "value": build_storage_body(row),
                    "representation": "storage",
                }
            },
        }

        if settings.confluence_parent_page_id:
            payload["ancestors"] = [
                {
                    "id": (
                        settings.confluence_parent_page_id
                    )
                }
            ]

        if settings.confluence_dry_run:
            print(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                )
            )
            continue

        response = session.post(
            f"{settings.atlassian_base_url}"
            "/wiki/rest/api/content",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        created = response.json()
        print(
            f"Created Confluence page "
            f"{created.get('id')}: {title}"
        )


if __name__ == "__main__":
    main()
