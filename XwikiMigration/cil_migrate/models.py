from dataclasses import dataclass


@dataclass
class PageRef:
    page_full_name: str
    page_name: str
    space: str


@dataclass
class AttachmentRecord:
    xwiki_page: str
    client_name: str
    filename: str
    mime_type: str
    size_bytes: int
    xwiki_download_url: str
