"""Descriptive statistics computed from the real scraped dataset."""
from __future__ import annotations

import pandas as pd

from analytics.data_cleaning import ensure_schema, with_parsed_dates


def compute_summary(df: pd.DataFrame) -> dict:
    """Headline metrics for the analytics dashboard."""
    df = ensure_schema(df)
    if df.empty:
        return {"total_records": 0, "unique_domains": 0, "avg_content_length": 0.0,
                "median_content_length": 0.0, "total_links": 0, "total_images": 0, "records_with_dates": 0}
    domains = df["domain"].replace("", pd.NA).dropna()
    return {
        "total_records": int(len(df)),
        "unique_domains": int(domains.nunique()),
        "avg_content_length": float(df["content_length"].mean()),
        "median_content_length": float(df["content_length"].median()),
        "total_links": int(df["links_count"].sum()),
        "total_images": int(df["image_count"].sum()),
        "records_with_dates": int((df["publication_date"] != "").sum()),
    }


def records_per_domain(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_schema(df)
    counts = df[df["domain"] != ""].groupby("domain").size().reset_index(name="records")
    return counts.sort_values("records", ascending=False).reset_index(drop=True)


def top_domains_by_content(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    df = ensure_schema(df)
    agg = (
        df[df["domain"] != ""].groupby("domain")
        .agg(total_characters=("content_length", "sum"), total_words=("word_count", "sum"), records=("url", "count"))
        .reset_index()
        .sort_values("total_characters", ascending=False)
        .head(top_n)
    )
    return agg.reset_index(drop=True)


def activity_over_time(df: pd.DataFrame, freq: str = "D") -> pd.DataFrame:
    """Records extracted per period (based on ``scraped_at``)."""
    parsed = with_parsed_dates(ensure_schema(df))["scraped_dt"].dropna()
    if parsed.empty:
        return pd.DataFrame(columns=["period", "records"])
    # Drop tz before period conversion to avoid pandas warnings.
    series = parsed.dt.tz_convert("UTC").dt.tz_localize(None)
    if freq == "H":
        grouped = series.dt.floor("h")
    else:
        grouped = series.dt.floor("D")
    out = grouped.value_counts().sort_index().reset_index()
    out.columns = ["period", "records"]
    return out


def publication_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Records per publication month (only records with a parsed date)."""
    parsed = with_parsed_dates(ensure_schema(df))["pub_dt"].dropna()
    if parsed.empty:
        return pd.DataFrame(columns=["month", "records"])
    months = parsed.dt.tz_convert("UTC").dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    out = months.value_counts().sort_index().reset_index()
    out.columns = ["month", "records"]
    return out
