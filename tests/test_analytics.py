import io

import pandas as pd
import pytest

from analytics import statistics as st_
from analytics import visualizations as viz
from analytics.data_cleaning import (clean_dataframe, ensure_schema, remove_duplicates, remove_empty_records,
                                     SCHEMA)
from analytics.keyword_analysis import extractive_summary, extract_keywords, rule_based_category, tokenize, top_keywords
from database.db_manager import DatabaseError, DatabaseManager
from database.models import ScrapeSession
from utils.exporters import build_filename, prepare_export_frame, record_to_text, to_csv_bytes, to_excel_bytes


def test_schema_and_empty():
    assert list(ensure_schema(None).columns) == SCHEMA
    assert list(ensure_schema(pd.DataFrame([{"url": "x"}])).columns[:len(SCHEMA)]) == SCHEMA


def test_duplicate_and_empty_removal(sample_df):
    assert len(sample_df) == 5
    dedup = remove_duplicates(sample_df)
    assert len(dedup) == 4
    assert len(remove_empty_records(dedup)) == 3


def test_clean_dataframe(sample_df):
    messy = sample_df.copy()
    messy.loc[0, "title"] = "  Padded  "
    messy.loc[0, "publication_date"] = "March 3 2024"
    out = clean_dataframe(messy)
    assert out.loc[0, "title"] == "Padded"
    assert out.loc[0, "publication_date"] == "2024-03-03"
    assert out.loc[0, "links_count"] == 2 and out.loc[0, "image_count"] == 1
    assert (out["content_length"] == out["content"].str.len()).all()


def test_keywords():
    assert "the" not in tokenize("The solar energy and the market")
    kw = top_keywords(["solar energy solar", "solar market"], 3)
    assert kw.iloc[0]["keyword"] == "solar" and kw.iloc[0]["count"] == 3
    assert extract_keywords("python python code code code data", 2) == ["code", "python"]
    bi = top_keywords(["solar energy rocks", "solar energy wins"], 1, bigrams=True)
    assert bi.iloc[0]["keyword"] == "solar energy"


def test_categories_and_summary():
    assert rule_based_category("The team won the league match after a late goal this season")[0] == "Sports"
    assert rule_based_category("hello world")[0] == "General / Other"
    text = " ".join(f"Sentence number {i} talks about solar energy markets and growth." for i in range(10))
    assert 0 < len(extractive_summary(text, 2)) < len(text)


def test_statistics(sample_df):
    df = remove_duplicates(sample_df)
    s = st_.compute_summary(df)
    assert s["total_records"] == 4 and s["unique_domains"] == 3 and s["total_links"] == 3
    assert s["records_with_dates"] == 2
    per = st_.records_per_domain(df)
    assert per.iloc[0]["domain"] == "a.com" and per.iloc[0]["records"] == 2
    assert st_.top_domains_by_content(df).iloc[0]["domain"] == "a.com"
    assert st_.activity_over_time(df)["records"].sum() == 4
    assert len(st_.publication_distribution(df)) == 2
    assert st_.compute_summary(ensure_schema(None))["total_records"] == 0
    assert st_.activity_over_time(ensure_schema(None)).empty


def test_figures(sample_df):
    df = remove_duplicates(sample_df)
    assert viz.content_length_histogram(df) is not None
    assert viz.records_per_domain_bar(st_.records_per_domain(df)) is not None
    assert viz.activity_line(st_.activity_over_time(df)) is not None
    assert viz.publication_bar(st_.publication_distribution(df)) is not None
    assert viz.keywords_bar(top_keywords(df["content"], 5)) is not None
    assert viz.publication_bar(pd.DataFrame(columns=["month", "records"])) is None


def test_exports(sample_df):
    csv = to_csv_bytes(sample_df).decode("utf-8-sig")
    header = csv.splitlines()[0]
    assert "Title" in header and "Publication Date" in header and "content_length" not in header
    xlsx = to_excel_bytes(sample_df)
    back = pd.read_excel(io.BytesIO(xlsx))
    assert len(back) == len(sample_df) and "Title" in back.columns
    flat = prepare_export_frame(sample_df, ["title", "links"])
    assert flat.loc[0, "Links"] == "https://a.com/2; https://x.com"
    nasty = sample_df.copy(); nasty.loc[0, "content"] = "bad\x00char\x07" + "x" * 40000
    assert len(to_excel_bytes(nasty)) > 0
    assert "Solar energy growth" in record_to_text(sample_df.iloc[0])
    assert build_filename("example.com", "complete", "csv").startswith("webscrape_example.com_complete_")
    assert "/" not in build_filename("../../etc", "x/y", "csv")


def test_database_roundtrip(tmp_path, sample_df):
    db = DatabaseManager(tmp_path / "t.db", tmp_path / "sessions")
    s = ScrapeSession("abcdef123456", "https://a.com/", "a.com", "2024-04-01T10:00:00+00:00", 5, 2, "completed", 3.2)
    db.save_session(s, sample_df)
    assert db.get_stats() == {"sessions": 1, "urls_processed": 2, "records": 5}
    loaded = db.load_dataset("abcdef123456")
    assert len(loaded) == 5 and loaded.loc[0, "links"] == ["https://a.com/2", "https://x.com"]
    assert db.list_sessions()[0].dataset_file == "abcdef123456.json"
    assert db.delete_session("abcdef123456") and db.load_dataset("abcdef123456") is None
    assert not (tmp_path / "sessions" / "abcdef123456.json").exists()


def test_database_security_and_clear(tmp_path, sample_df):
    db = DatabaseManager(tmp_path / "t.db", tmp_path / "sessions")
    assert db.get_session("../../etc/passwd") is None
    with pytest.raises(DatabaseError):
        db.save_session(ScrapeSession("../evil", "u", "d", "t", 0, 0, "x", 0), None)
    for i in range(3):
        db.save_session(ScrapeSession(f"00000000000{i}", "https://a.com/", "a.com", f"2024-04-0{i+1}T00:00:00", 5, 1, "completed", 1), sample_df)
    assert db.clear_history() == 3 and db.list_sessions() == []
    assert list((tmp_path / "sessions").glob("*.json")) == []
