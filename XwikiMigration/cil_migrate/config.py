from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    root: Path = Path(__file__).resolve().parents[1]

    xwiki_base_url: str = os.getenv("XWIKI_BASE_URL", "").rstrip("/")
    xwiki_wiki_name: str = os.getenv("XWIKI_WIKI_NAME", "xwiki")
    xwiki_username: str = os.getenv("XWIKI_USERNAME", "")
    xwiki_password: str = os.getenv("XWIKI_PASSWORD", "")
    xwiki_verify_ssl: bool = as_bool(os.getenv("XWIKI_VERIFY_SSL"), False)
    xwiki_class_name: str = os.getenv(
        "XWIKI_CLASS_NAME",
        "ClientInfoLibraryCode.ClientInfoLibraryClass",
    )
    xwiki_space: str = os.getenv("XWIKI_SPACE", "Client Info Library")

    atlassian_base_url: str = os.getenv("ATLASSIAN_BASE_URL", "").rstrip("/")
    atlassian_email: str = os.getenv("ATLASSIAN_EMAIL", "")
    atlassian_api_token: str = os.getenv("ATLASSIAN_API_TOKEN", "")

    confluence_space_key: str = os.getenv("CONFLUENCE_SPACE_KEY", "CIL")
    confluence_parent_page_id: str = os.getenv("CONFLUENCE_PARENT_PAGE_ID", "")
    confluence_dry_run: bool = as_bool(os.getenv("CONFLUENCE_DRY_RUN"), True)

    jira_assets_workspace_id: str = os.getenv("JIRA_ASSETS_WORKSPACE_ID", "")
    jira_assets_object_type_id: str = os.getenv("JIRA_ASSETS_OBJECT_TYPE_ID", "")
    jira_assets_dry_run: bool = as_bool(os.getenv("JIRA_ASSETS_DRY_RUN"), True)

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def clients_dir(self) -> Path:
        return self.output_dir / "clients"

    @property
    def inventory_dir(self) -> Path:
        return self.output_dir / "inventory"

    @property
    def attachments_dir(self) -> Path:
        return self.output_dir / "attachments"

    @property
    def logs_dir(self) -> Path:
        return self.output_dir / "logs"

    def ensure_dirs(self) -> None:
        for path in [
            self.clients_dir,
            self.inventory_dir,
            self.attachments_dir,
            self.logs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def validate_xwiki(self) -> None:
        missing = []
        if not self.xwiki_base_url:
            missing.append("XWIKI_BASE_URL")
        if not self.xwiki_username:
            missing.append("XWIKI_USERNAME")
        if not self.xwiki_password:
            missing.append("XWIKI_PASSWORD")
        if missing:
            raise RuntimeError("Missing: " + ", ".join(missing))


settings = Settings()
settings.ensure_dirs()
