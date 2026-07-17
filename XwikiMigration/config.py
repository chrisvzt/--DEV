from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv:
    load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    project_root: Path = Path(__file__).resolve().parent
    output_root: Path = project_root / "output"

    xwiki_base_url: str = os.getenv(
        "XWIKI_BASE_URL",
        "https://wikistage.llts.com:8181/xwiki",
    ).rstrip("/")
    xwiki_wiki_name: str = os.getenv("XWIKI_WIKI_NAME", "xwiki")
    xwiki_username: str = os.getenv("XWIKI_USERNAME", "")
    xwiki_password: str = os.getenv("XWIKI_PASSWORD", "")
    xwiki_verify_ssl: bool = _as_bool(
        os.getenv("XWIKI_VERIFY_SSL"),
        default=False,
    )
    xwiki_class_name: str = os.getenv(
        "XWIKI_CLASS_NAME",
        "ClientInfoLibraryCode.ClientInfoLibraryClass",
    )
    xwiki_space: str = os.getenv(
        "XWIKI_SPACE",
        "Client Info Library",
    )

    atlassian_base_url: str = os.getenv(
        "ATLASSIAN_BASE_URL",
        "",
    ).rstrip("/")
    atlassian_email: str = os.getenv("ATLASSIAN_EMAIL", "")
    atlassian_api_token: str = os.getenv("ATLASSIAN_API_TOKEN", "")

    confluence_space_key: str = os.getenv(
        "CONFLUENCE_SPACE_KEY",
        "CIL",
    )
    confluence_parent_page_id: str = os.getenv(
        "CONFLUENCE_PARENT_PAGE_ID",
        "",
    )
    confluence_dry_run: bool = _as_bool(
        os.getenv("CONFLUENCE_DRY_RUN"),
        default=True,
    )

    jira_assets_workspace_id: str = os.getenv(
        "JIRA_ASSETS_WORKSPACE_ID",
        "",
    )
    jira_assets_schema_id: str = os.getenv(
        "JIRA_ASSETS_SCHEMA_ID",
        "",
    )
    jira_assets_object_type_id: str = os.getenv(
        "JIRA_ASSETS_OBJECT_TYPE_ID",
        "",
    )
    jira_assets_dry_run: bool = _as_bool(
        os.getenv("JIRA_ASSETS_DRY_RUN"),
        default=True,
    )

    @property
    def inventory_dir(self) -> Path:
        return self.output_root / "inventory"

    @property
    def attachments_dir(self) -> Path:
        return self.output_root / "attachments"

    @property
    def clients_dir(self) -> Path:
        return self.output_root / "clients"

    @property
    def logs_dir(self) -> Path:
        return self.output_root / "logs"

    def ensure_directories(self) -> None:
        for path in (
            self.output_root,
            self.inventory_dir,
            self.attachments_dir,
            self.clients_dir,
            self.logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def validate_xwiki(self) -> None:
        missing = []
        if not self.xwiki_username:
            missing.append("XWIKI_USERNAME")
        if not self.xwiki_password:
            missing.append("XWIKI_PASSWORD")
        if missing:
            raise RuntimeError(
                "Missing XWiki environment variables: "
                + ", ".join(missing)
            )

    def validate_atlassian(self) -> None:
        missing = []
        if not self.atlassian_base_url:
            missing.append("ATLASSIAN_BASE_URL")
        if not self.atlassian_email:
            missing.append("ATLASSIAN_EMAIL")
        if not self.atlassian_api_token:
            missing.append("ATLASSIAN_API_TOKEN")
        if missing:
            raise RuntimeError(
                "Missing Atlassian environment variables: "
                + ", ".join(missing)
            )


settings = Settings()
settings.ensure_directories()
