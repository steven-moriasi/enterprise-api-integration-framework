from collections.abc import Mapping
from typing import Generic, TypeVar
from urllib.parse import urlparse

from pydantic import BaseModel

Item = TypeVar("Item")


class CursorPage(BaseModel, Generic[Item]):
    items: list[Item]
    next_cursor: str | None = None


def next_page_number(current_page: int, total_pages: int) -> int | None:
    if current_page < 1 or total_pages < current_page:
        raise ValueError("Invalid page bounds")
    if current_page == total_pages:
        return None
    return current_page + 1


def next_link(
    headers: Mapping[str, str],
    *,
    expected_origin: str,
) -> str | None:
    link_header = headers.get("link")
    if not link_header:
        return None

    for entry in link_header.split(","):
        segments = [segment.strip() for segment in entry.split(";")]
        if len(segments) < 2 or 'rel="next"' not in segments[1:]:
            continue
        target = segments[0]
        if not target.startswith("<") or not target.endswith(">"):
            raise ValueError("Invalid Link header")
        url = target[1:-1]
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin != expected_origin.rstrip("/"):
            raise ValueError("Cross-origin pagination link rejected")
        return url
    return None
