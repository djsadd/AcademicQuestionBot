"""Parse Platonus academic calendar HTML."""
from __future__ import annotations

from html.parser import HTMLParser


def _normalize(text: str) -> str:
    return " ".join(text.split())


class _CalendarHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.sections: list[dict] = []
        self._current_section: dict | None = None
        self._pending_name: str | None = None
        self._cell_type: str | None = None
        self._cell_parts: list[str] = []
        self._in_header = False
        self._header_parts: list[str] = []
        self._in_plain_header = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key: value or "" for key, value in attrs}
        class_attr = attrs_map.get("class", "")

        if tag in {"h4", "h5"}:
            self._in_header = True
            self._header_parts = []
            return

        if tag == "td" and "plainHeader" in class_attr:
            self._in_plain_header = True
            self._title_parts = []
            return

        if tag == "td" and "tdPeriodName" in class_attr:
            self._cell_type = "name"
            self._cell_parts = []
            return

        if tag == "td" and "tdPeriod" in class_attr:
            self._cell_type = "value"
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h4", "h5"} and self._in_header:
            title = _normalize("".join(self._header_parts))
            self._in_header = False
            if title:
                self._current_section = {"title": title, "items": []}
                self.sections.append(self._current_section)
            return

        if tag == "td" and self._in_plain_header:
            self._in_plain_header = False
            self.title = _normalize("".join(self._title_parts))
            return

        if tag == "td" and self._cell_type:
            text = _normalize("".join(self._cell_parts))
            if self._cell_type == "name":
                self._pending_name = text
            elif self._cell_type == "value":
                if self._pending_name and text:
                    if self._current_section is None:
                        self._current_section = {"title": "General", "items": []}
                        self.sections.append(self._current_section)
                    self._current_section["items"].append(
                        {"name": self._pending_name, "period": text}
                    )
                self._pending_name = None
            self._cell_type = None
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_plain_header:
            self._title_parts.append(data)
            return
        if self._in_header:
            self._header_parts.append(data)
            return
        if self._cell_type:
            self._cell_parts.append(data)


def parse_calendar_html(html: str) -> dict:
    parser = _CalendarHTMLParser()
    parser.feed(html)
    return {"title": parser.title, "sections": parser.sections}
