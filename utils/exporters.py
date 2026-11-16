"""CSV / Excel / text exports with clean column names."""
from __future__ import annotations

import io
import re
from datetime import datetime

import pandas as pd

from analytics.data_cleaning import ensure_schema
from utils.helpers import safe_filename

EXPORT_COLUMNS = {
    "title": "Title", "url": "URL", "domain": "Domain", "publication_date": "Publication Date",
    "meta_description": "Meta Description", "h1": "H1 Headings", "h2": "H2 Headings", "h3": "H3 Headings",
    "paragraphs": "Paragraphs", "content": "Content", "word_count": "Word Count",
    "content_length": "Content Length", "links_count": "Link Count", "links": "Links",
    "image_count": "Image Count", "images": "Images", "price": "Price", "record_type": "Record Type",
    "template": "Template", "status_code": "HTTP Status", "scraped_at": "Scraped At",
    "extraction_notes": "Extraction Notes",
}
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
EXCEL_CELL_LIMIT = 32_000


class ExportError(Exception):
    """Raised with a user-friendly message when an export cannot be produced."""


def _flatten_value(value) -> str:
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.append(f"{item.get('src', '')} ({item.get('alt', '')})" if isinstance(item, dict) else str(item))
        return "; ".join(parts)
    return "" if value is None else str(value)


def prepare_export_frame(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Flatten list columns and rename to human-friendly headers."""
    data = ensure_schema(df)
    cols = [c for c in (columns or list(EXPORT_COLUMNS)) if c in data.columns]
    out = data[cols].copy()
    for col in cols:
        if out[col].map(lambda v: isinstance(v, list)).any():
            out[col] = out[col].map(_flatten_value)
    return out.rename(columns={c: EXPORT_COLUMNS.get(c, c.replace("_", " ").title()) for c in cols})


def to_csv_bytes(df: pd.DataFrame, columns: list[str] | None = None) -> bytes:
    """UTF-8 CSV with BOM so Excel opens it correctly."""
    frame = prepare_export_frame(df, columns)
    return frame.to_csv(index=False).encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame, columns: list[str] | None = None, sheet_name: str = "Scraped Data") -> bytes:
    frame = prepare_export_frame(df, columns)
    for col in frame.columns:
        if frame[col].dtype == object or str(frame[col].dtype).startswith("str"):
            frame[col] = frame[col].astype(str).map(lambda s: _ILLEGAL_XML.sub("", s)[:EXCEL_CELL_LIMIT])
    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])
            sheet = writer.sheets[sheet_name[:31]]
            sheet.freeze_panes = "A2"
            for idx, col in enumerate(frame.columns, start=1):
                longest = max([len(str(col))] + [len(str(v)) for v in frame[col].head(200)])
                sheet.column_dimensions[sheet.cell(row=1, column=idx).column_letter].width = min(max(12, longest + 2), 60)
    except Exception as exc:
        raise ExportError("The Excel file could not be created. Try the CSV export instead.") from exc
    return buffer.getvalue()


def record_to_text(record: pd.Series | dict) -> str:
    """Readable plain-text rendering of one record."""
    r = dict(record)
    lines = [
        f"Title: {r.get('title', '')}", f"URL: {r.get('url', '')}", f"Domain: {r.get('domain', '')}",
        f"Published: {r.get('publication_date') or 'n/a'}", f"Scraped at: {r.get('scraped_at', '')}",
    ]
    if r.get("price"):
        lines.append(f"Price: {r['price']}")
    if r.get("meta_description"):
        lines += ["", "Description:", str(r["meta_description"])]
    for level in ("h1", "h2", "h3"):
        if isinstance(r.get(level), list) and r[level]:
            lines += ["", f"{level.upper()} headings:"] + [f"  - {h}" for h in r[level]]
    lines += ["", "Content:", str(r.get("content") or r.get("paragraphs") or "")]
    return "\n".join(lines).strip() + "\n"


def build_filename(domain_hint: str, kind: str, ext: str, now: datetime | None = None) -> str:
    """e.g. ``webscrape_example.com_complete_20260101_1230.csv``."""
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M")
    return f"webscrape_{safe_filename(domain_hint, 'dataset')}_{safe_filename(kind, 'data')}_{stamp}.{ext}"
