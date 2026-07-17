from __future__ import annotations

import html
from typing import Any
from urllib.parse import quote, unquote

import requests
import urllib3
from requests.auth import HTTPBasicAuth

from config import settings


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NonCILPageError(Exception):
    """Raised when a page exists but has no CIL object."""


class XWikiClient:
    def __init__(self) -> None:
        settings.validate_xwiki()

        self.session = requests.Session()
        self.session.verify = settings.xwiki_verify_ssl
        self.session.auth = HTTPBasicAuth(
            settings.xwiki_username,
            settings.xwiki_password,
        )
        self.session.headers.update(
            {"Accept": "application/json"}
        )

    @staticmethod
    def find_link(
        item: dict[str, Any],
        relation_suffix: str,
    ) -> str | None:
        links = item.get("links", [])
        if isinstance(links, dict):
            links = [links]

        for link in links:
            if not isinstance(link, dict):
                continue
            href = link.get("href", "")
            relation = link.get("rel", "")
            if href and relation.endswith(relation_suffix):
                return href

        return None

    @staticmethod
    def normalize_object_summaries(
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        summaries = (
            data.get("objectSummaries")
            or data.get("objectSummary")
            or data.get("objects")
            or []
        )

        if isinstance(summaries, dict):
            summaries = summaries.get(
                "objectSummary",
                summaries,
            )

        if isinstance(summaries, dict):
            summaries = [summaries]

        return [
            item for item in summaries
            if isinstance(item, dict)
        ] if isinstance(summaries, list) else []

    @staticmethod
    def normalize_properties(
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        properties = data.get("properties", [])

        if isinstance(properties, dict):
            properties = properties.get(
                "property",
                properties,
            )

        if isinstance(properties, dict):
            properties = [properties]

        return [
            item for item in properties
            if isinstance(item, dict)
        ] if isinstance(properties, list) else []

    @staticmethod
    def normalize_attachment_summaries(
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        summaries = (
            data.get("attachmentSummaries")
            or data.get("attachmentSummary")
            or data.get("attachments")
            or []
        )

        if isinstance(summaries, dict):
            summaries = summaries.get(
                "attachmentSummary",
                summaries,
            )

        if isinstance(summaries, dict):
            summaries = [summaries]

        return [
            item for item in summaries
            if isinstance(item, dict)
        ] if isinstance(summaries, list) else []

    def build_page_url(
        self,
        page: dict[str, str],
    ) -> str:
        page_name = page.get("page_name", "")
        space = page.get(
            "space",
            settings.xwiki_space,
        )

        if not page_name:
            raise ValueError(
                f"No pageName for {page.get('page_full_name', '')!r}"
            )

        return (
            f"{settings.xwiki_base_url}/rest/wikis/"
            f"{settings.xwiki_wiki_name}/spaces/"
            f"{quote(space, safe='')}/pages/"
            f"{quote(page_name, safe='')}"
        )

    def get_page_batch(
        self,
        start: int,
        batch_size: int,
        visible_only: bool = True,
    ) -> list[dict[str, str]]:
        url = (
            f"{settings.xwiki_base_url}/rest/wikis/"
            f"{settings.xwiki_wiki_name}/query"
        )

        hidden_filter = (
            "\nand doc.hidden = 0"
            if visible_only
            else ""
        )
        query = (
            f"where doc.space = '{settings.xwiki_space}'"
            f"{hidden_filter}"
        )

        response = self.session.get(
            url,
            params={
                "q": query,
                "type": "hql",
                "number": batch_size,
                "start": start,
            },
            timeout=60,
        )
        response.raise_for_status()

        results = response.json().get(
            "searchResults",
            [],
        )

        return [
            {
                "page_full_name": item.get(
                    "pageFullName",
                    "",
                ),
                "page_name": item.get(
                    "pageName",
                    "",
                ),
                "space": item.get(
                    "space",
                    settings.xwiki_space,
                ),
            }
            for item in results
        ]

    def get_page_metadata(
        self,
        page: dict[str, str],
    ) -> tuple[dict[str, Any], str]:
        page_url = self.build_page_url(page)

        response = self.session.get(
            page_url,
            timeout=60,
        )
        response.raise_for_status()

        return response.json(), page_url

    def get_cil_properties(
        self,
        page: dict[str, str],
        page_metadata: dict[str, Any],
        page_url: str,
    ) -> tuple[dict[str, Any], str]:
        objects_url = (
            self.find_link(
                page_metadata,
                "/objects",
            )
            or f"{page_url}/objects"
        )

        response = self.session.get(
            objects_url,
            timeout=60,
        )
        response.raise_for_status()

        summaries = self.normalize_object_summaries(
            response.json()
        )

        matching = next(
            (
                item for item in summaries
                if item.get("className")
                == settings.xwiki_class_name
            ),
            None,
        )

        if not matching:
            raise NonCILPageError(
                f"No {settings.xwiki_class_name} object."
            )

        properties_url = self.find_link(
            matching,
            "/properties",
        )

        if not properties_url:
            object_url = self.find_link(
                matching,
                "/object",
            )
            if object_url:
                properties_url = (
                    f"{object_url.rstrip('/')}/properties"
                )

        if not properties_url:
            number = matching.get("number")
            if number is None:
                raise ValueError(
                    "CIL object has no object number."
                )

            class_name = quote(
                settings.xwiki_class_name,
                safe=".",
            )
            properties_url = (
                f"{page_url}/objects/"
                f"{class_name}/{number}/properties"
            )

        response = self.session.get(
            properties_url,
            timeout=60,
        )
        response.raise_for_status()

        return response.json(), properties_url

    def extract_field_values(
        self,
        properties_response: dict[str, Any],
    ) -> dict[str, Any]:
        values: dict[str, Any] = {}

        for item in self.normalize_properties(
            properties_response
        ):
            name = item.get("name")
            if name:
                values[name] = item.get(
                    "value",
                    "",
                )

        return values

    def get_attachments(
        self,
        page: dict[str, str],
        page_metadata: dict[str, Any],
        page_url: str,
    ) -> tuple[list[dict[str, Any]], str]:
        attachments_url = (
            self.find_link(
                page_metadata,
                "/attachments",
            )
            or f"{page_url}/attachments"
        )

        response = self.session.get(
            attachments_url,
            timeout=60,
        )

        if response.status_code == 404:
            return [], attachments_url

        response.raise_for_status()

        return (
            self.normalize_attachment_summaries(
                response.json()
            ),
            attachments_url,
        )

    def get_attachment_filename(
        self,
        attachment: dict[str, Any],
    ) -> str:
        return (
            attachment.get("name")
            or attachment.get("filename")
            or attachment.get("fileName")
            or ""
        )

    def get_attachment_download_url(
        self,
        attachment: dict[str, Any],
        page_url: str,
        filename: str,
    ) -> str:
        for suffix in (
            "/attachment",
            "/download",
            "/content",
        ):
            value = self.find_link(
                attachment,
                suffix,
            )
            if value:
                return value

        if attachment.get("href"):
            return str(attachment["href"])

        return (
            f"{page_url}/attachments/"
            f"{quote(filename, safe='')}"
        )

    def download(
        self,
        url: str,
        destination,
        chunk_size: int = 1024 * 1024,
    ) -> int:
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        response = self.session.get(
            url,
            stream=True,
            timeout=180,
            headers={"Accept": "*/*"},
        )
        response.raise_for_status()

        total = 0
        with destination.open("wb") as output:
            for chunk in response.iter_content(
                chunk_size=chunk_size
            ):
                if chunk:
                    output.write(chunk)
                    total += len(chunk)

        return total

    @staticmethod
    def normalize_reference_text(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return unquote(
            html.unescape(str(value))
        ).casefold()

    def find_referencing_fields(
        self,
        filename: str,
        field_values: dict[str, Any],
    ) -> list[str]:
        needle = self.normalize_reference_text(
            filename
        )

        if not needle:
            return []

        return [
            name
            for name, value in field_values.items()
            if needle in self.normalize_reference_text(
                value
            )
        ]
