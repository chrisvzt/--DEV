from __future__ import annotations

import html
from typing import Any
from urllib.parse import quote, unquote

import requests
import urllib3
from requests.auth import HTTPBasicAuth
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings
from .models import PageRef

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NonCILPageError(Exception):
    pass


class XWikiClient:
    def __init__(self) -> None:
        settings.validate_xwiki()

        self.session = requests.Session()
        self.session.verify = settings.xwiki_verify_ssl
        self.session.auth = HTTPBasicAuth(
            settings.xwiki_username,
            settings.xwiki_password,
        )
        self.session.headers.update({"Accept": "application/json"})

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def get_json(self, url: str, **kwargs) -> dict[str, Any]:
        response = self.session.get(url, timeout=60, **kwargs)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def find_link(item: dict[str, Any], suffix: str) -> str | None:
        links = item.get("links", [])
        if isinstance(links, dict):
            links = [links]

        for link in links:
            if (
                isinstance(link, dict)
                and link.get("href")
                and str(link.get("rel", "")).endswith(suffix)
            ):
                return str(link["href"])
        return None

    @staticmethod
    def normalize_list(data: Any, wrapper_keys: tuple[str, ...]) -> list[dict]:
        value = data
        if isinstance(value, dict):
            for key in wrapper_keys:
                if key in value:
                    value = value[key]
                    break

        if isinstance(value, dict):
            for key in wrapper_keys:
                if key in value:
                    value = value[key]
                    break

        if isinstance(value, dict):
            value = [value]

        if not isinstance(value, list):
            return []

        return [item for item in value if isinstance(item, dict)]

    def build_page_url(self, page: PageRef) -> str:
        return (
            f"{settings.xwiki_base_url}/rest/wikis/"
            f"{settings.xwiki_wiki_name}/spaces/"
            f"{quote(page.space, safe='')}/pages/"
            f"{quote(page.page_name, safe='')}"
        )

    def get_page_batch(
        self,
        start: int,
        batch_size: int,
        visible_only: bool = True,
    ) -> list[PageRef]:
        url = (
            f"{settings.xwiki_base_url}/rest/wikis/"
            f"{settings.xwiki_wiki_name}/query"
        )

        query = f"where doc.space = '{settings.xwiki_space}'"
        if visible_only:
            query += "\nand doc.hidden = 0"

        data = self.get_json(
            url,
            params={
                "q": query,
                "type": "hql",
                "number": batch_size,
                "start": start,
            },
        )

        return [
            PageRef(
                page_full_name=item.get("pageFullName", ""),
                page_name=item.get("pageName", ""),
                space=item.get("space", settings.xwiki_space),
            )
            for item in data.get("searchResults", [])
        ]

    def get_page_metadata(self, page: PageRef) -> tuple[dict, str]:
        page_url = self.build_page_url(page)
        return self.get_json(page_url), page_url

    def get_cil_properties(
        self,
        page: PageRef,
        metadata: dict,
        page_url: str,
    ) -> tuple[dict, str]:
        objects_url = self.find_link(metadata, "/objects") or f"{page_url}/objects"
        objects_data = self.get_json(objects_url)

        summaries = self.normalize_list(
            objects_data,
            ("objectSummaries", "objectSummary", "objects"),
        )

        matching = next(
            (
                item
                for item in summaries
                if item.get("className") == settings.xwiki_class_name
            ),
            None,
        )

        if not matching:
            raise NonCILPageError(
                f"No {settings.xwiki_class_name} object on {page.page_full_name}"
            )

        properties_url = self.find_link(matching, "/properties")

        if not properties_url:
            object_url = self.find_link(matching, "/object")
            if object_url:
                properties_url = f"{object_url.rstrip('/')}/properties"

        if not properties_url:
            number = matching.get("number")
            if number is None:
                raise ValueError("CIL object has no number.")

            class_name = quote(settings.xwiki_class_name, safe=".")
            properties_url = (
                f"{page_url}/objects/{class_name}/{number}/properties"
            )

        return self.get_json(properties_url), properties_url

    def extract_values(self, properties_data: dict) -> dict[str, Any]:
        items = self.normalize_list(
            properties_data,
            ("properties", "property"),
        )

        return {
            item["name"]: item.get("value", "")
            for item in items
            if item.get("name")
        }

    def get_attachments(
        self,
        metadata: dict,
        page_url: str,
    ) -> tuple[list[dict], str]:
        url = self.find_link(metadata, "/attachments") or f"{page_url}/attachments"

        response = self.session.get(url, timeout=60)
        if response.status_code == 404:
            return [], url

        response.raise_for_status()
        data = response.json()

        return (
            self.normalize_list(
                data,
                (
                    "attachmentSummaries",
                    "attachmentSummary",
                    "attachments",
                ),
            ),
            url,
        )

    def attachment_filename(self, attachment: dict) -> str:
        return (
            attachment.get("name")
            or attachment.get("filename")
            or attachment.get("fileName")
            or ""
        )

    def attachment_download_url(
        self,
        attachment: dict,
        page_url: str,
        filename: str,
    ) -> str:
        for suffix in ("/attachment", "/download", "/content"):
            url = self.find_link(attachment, suffix)
            if url:
                return url

        if attachment.get("href"):
            return str(attachment["href"])

        return f"{page_url}/attachments/{quote(filename, safe='')}"

    @staticmethod
    def normalized_text(value: Any) -> str:
        return unquote(html.unescape(str(value or ""))).casefold()

    def referencing_fields(
        self,
        filename: str,
        values: dict[str, Any],
    ) -> list[str]:
        needle = self.normalized_text(filename)
        if not needle:
            return []

        return [
            key
            for key, value in values.items()
            if needle in self.normalized_text(value)
        ]
