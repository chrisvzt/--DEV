from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from config import settings


# Replace these placeholders with actual Jira Assets attribute IDs
# after the target object type is created.
ATTRIBUTE_MAP = {
    "clientname": "ATTR_CLIENT_NAME",
    "Business_System": "ATTR_BUSINESS_SYSTEM",
    "legalentity": "ATTR_LEGAL_ENTITY",
    "cid": "ATTR_CID",
    "lead": "ATTR_LEAD",
    "pmlead": "ATTR_PM_LEAD",
    "parentcompany": "ATTR_PARENT_COMPANY",
    "childcompany": "ATTR_CHILD_COMPANY",
    "notesissues": "ATTR_NOTES",
}


def build_object_payload(
    row: dict[str, str],
) -> dict:
    attributes = []

    for source_field, attribute_id in (
        ATTRIBUTE_MAP.items()
    ):
        value = row.get(source_field, "")
        if not value:
            continue

        attributes.append(
            {
                "objectTypeAttributeId": attribute_id,
                "objectAttributeValues": [
                    {"value": value}
                ],
            }
        )

    return {
        "objectTypeId": (
            settings.jira_assets_object_type_id
        ),
        "attributes": attributes,
    }


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

    if not settings.jira_assets_workspace_id:
        raise RuntimeError(
            "JIRA_ASSETS_WORKSPACE_ID is required."
        )
    if not settings.jira_assets_object_type_id:
        raise RuntimeError(
            "JIRA_ASSETS_OBJECT_TYPE_ID is required."
        )

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

    endpoint = (
        f"{settings.atlassian_base_url}"
        "/gateway/api/jsm/assets/workspace/"
        f"{settings.jira_assets_workspace_id}/v1/object/create"
    )

    for row in rows[: args.limit]:
        payload = build_object_payload(row)

        if settings.jira_assets_dry_run:
            print(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                )
            )
            continue

        response = session.post(
            endpoint,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        created = response.json()
        print(
            "Created Assets object:",
            created.get("id"),
            row.get("clientname"),
        )


if __name__ == "__main__":
    main()
