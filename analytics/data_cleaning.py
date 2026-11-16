"""Schema enforcement and cleaning for scraped datasets."""
from __future__ import annotations

import pandas as pd

LIST_COLUMNS = ["h1", "h2", "h3", "links", "images"]
TEXT_COLUMNS = [
    "url", "domain", "title", "meta_description", "paragraphs", "content", "publication_date",
    "price", "record_type", "template", "scraped_at", "extraction_notes",
]
NUMERIC_COLUMNS = ["word_count", "content_length", "links_count", "image_count", "status_code"]
SCHEMA = [
    "url", "domain", "title", "meta_description", "h1", "h2", "h3", "paragraphs", "content",
    "word_count", "content_length", "links", "links_count", "images", "image_count",
    "publication_date", "price", "record_type", "template", "status_code", "scraped_at",
    "extraction_notes",
]


def records_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """Build a cleaned, schema-conformant DataFrame (derived counts/lengths recomputed)."""
    return clean_dataframe(pd.DataFrame(records))


def ensure_schema(df: pd.DataFrame | None) -> pd.DataFrame:
    """Return a copy containing every schema column with sane types."""
    if df is None or df.empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in SCHEMA}).astype(
            {c: "float64" if c in NUMERIC_COLUMNS else "object" for c in SCHEMA}
        )
    out = df.copy()
    for col in SCHEMA:
        if col not in out.columns:
            if col in LIST_COLUMNS:
                out[col] = [[] for _ in range(len(out))]
            elif col in NUMERIC_COLUMNS:
                out[col] = 0.0
            else:
                out[col] = ""
    for col in TEXT_COLUMNS:
        out[col] = out[col].fillna("").astype(str)
    for col in NUMERIC_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ("word_count", "content_length", "links_count", "image_count"):
        out[col] = out[col].fillna(0)
    for col in LIST_COLUMNS:
        out[col] = out[col].apply(lambda v: v if isinstance(v, list) else [])
    return out[SCHEMA + [c for c in out.columns if c not in SCHEMA]].reset_index(drop=True)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Strip text fields, recompute derived lengths and normalise dates."""
    out = ensure_schema(df)
    for col in ("title", "meta_description", "domain", "url", "price"):
        out[col] = out[col].str.strip()
    out["content"] = out["content"].str.replace(r"[ \t]+", " ", regex=True).str.strip()
    out["content_length"] = out["content"].str.len()
    out["word_count"] = out["content"].str.split().str.len().fillna(0)
    out["links_count"] = out["links"].apply(len)
    out["image_count"] = out["images"].apply(len)
    parsed = pd.to_datetime(out["publication_date"], errors="coerce", utc=True)
    out["publication_date"] = parsed.dt.strftime("%Y-%m-%d").fillna("")
    return out


def remove_duplicates(df: pd.DataFrame, subset: list[str] | None = None) -> pd.DataFrame:
    """Drop duplicate records (default key: url + title + price)."""
    out = ensure_schema(df)
    subset = subset or ["url", "title", "price"]
    return out.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)


def remove_empty_records(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that have neither a title nor any text content."""
    out = ensure_schema(df)
    has_title = out["title"].str.strip() != ""
    has_text = (out["content"].str.strip() != "") | (out["paragraphs"].str.strip() != "")
    return out[has_title | has_text].reset_index(drop=True)


def with_parsed_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``pub_dt`` / ``scraped_dt`` datetime columns (UTC, NaT when missing)."""
    out = df.copy()
    out["pub_dt"] = pd.to_datetime(out["publication_date"], errors="coerce", utc=True)
    out["scraped_dt"] = pd.to_datetime(out["scraped_at"], errors="coerce", utc=True)
    return out
