"""Plotly figure builders (dark theme). Each returns ``None`` when there is nothing to plot."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from analytics.data_cleaning import ensure_schema

PALETTE = ["#7C5CFF", "#22D3EE", "#F59E0B", "#10B981", "#F43F5E", "#60A5FA", "#A78BFA", "#34D399"]
PRIMARY = PALETTE[0]
ACCENT = PALETTE[1]


def _style(fig: go.Figure, title: str, height: int = 340) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        title={"text": title, "x": 0.01, "font": {"size": 16}},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        height=height,
        font={"family": "Inter, Segoe UI, sans-serif"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        hoverlabel={"bgcolor": "#1B2440"},
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
    return fig


def content_length_histogram(df: pd.DataFrame) -> go.Figure | None:
    df = ensure_schema(df)
    data = df[df["content_length"] > 0]
    if data.empty:
        return None
    fig = px.histogram(data, x="content_length", nbins=min(30, max(5, len(data))),
                       color_discrete_sequence=[PRIMARY], labels={"content_length": "Content length (characters)"})
    fig.update_traces(hovertemplate="Length: %{x}<br>Records: %{y}<extra></extra>")
    fig.update_layout(yaxis_title="Records", bargap=0.05)
    return _style(fig, "Content length distribution")


def records_per_domain_bar(counts: pd.DataFrame, top_n: int = 15) -> go.Figure | None:
    if counts.empty:
        return None
    data = counts.head(top_n).sort_values("records")
    fig = px.bar(data, x="records", y="domain", orientation="h", color_discrete_sequence=[ACCENT],
                 labels={"records": "Records", "domain": "Domain"})
    fig.update_traces(hovertemplate="%{y}<br>Records: %{x}<extra></extra>")
    return _style(fig, "Records per domain")


def activity_line(activity: pd.DataFrame) -> go.Figure | None:
    if activity.empty:
        return None
    fig = px.area(activity, x="period", y="records", markers=True, color_discrete_sequence=[PRIMARY],
                  labels={"period": "Date", "records": "Records extracted"})
    fig.update_traces(hovertemplate="%{x|%b %d, %Y %H:%M}<br>Records: %{y}<extra></extra>")
    return _style(fig, "Extraction activity over time")


def publication_bar(dist: pd.DataFrame) -> go.Figure | None:
    if dist.empty:
        return None
    fig = px.bar(dist, x="month", y="records", color_discrete_sequence=[ACCENT],
                 labels={"month": "Publication month", "records": "Records"})
    fig.update_traces(hovertemplate="%{x|%b %Y}<br>Records: %{y}<extra></extra>")
    return _style(fig, "Publication date distribution")


def top_domains_bar(top: pd.DataFrame) -> go.Figure | None:
    if top.empty:
        return None
    data = top.sort_values("total_characters")
    fig = px.bar(data, x="total_characters", y="domain", orientation="h", color="records",
                 color_continuous_scale=["#2B2F66", PRIMARY, ACCENT],
                 labels={"total_characters": "Extracted characters", "domain": "Domain", "records": "Records"})
    fig.update_traces(hovertemplate="%{y}<br>Characters: %{x:,}<extra></extra>")
    return _style(fig, "Top domains by extracted content")


def keywords_bar(keywords: pd.DataFrame, title: str = "Most frequent keywords") -> go.Figure | None:
    if keywords.empty:
        return None
    data = keywords.sort_values("count")
    fig = px.bar(data, x="count", y="keyword", orientation="h", color="count",
                 color_continuous_scale=["#2B2F66", PRIMARY, ACCENT], labels={"count": "Occurrences", "keyword": "Keyword"})
    fig.update_layout(coloraxis_showscale=False)
    fig.update_traces(hovertemplate="%{y}: %{x}<extra></extra>")
    return _style(fig, title, height=max(320, 22 * len(data) + 100))


def category_donut(counts: pd.DataFrame) -> go.Figure | None:
    if counts.empty:
        return None
    fig = px.pie(counts, names="category", values="records", hole=0.55, color_discrete_sequence=PALETTE)
    fig.update_traces(hovertemplate="%{label}: %{value} records<extra></extra>")
    return _style(fig, "Content categories")


def sessions_activity_bar(sessions: pd.DataFrame) -> go.Figure | None:
    """Overview chart for the home page: records extracted per day across sessions."""
    if sessions.empty:
        return None
    data = sessions.copy()
    data["day"] = pd.to_datetime(data["created_at"], errors="coerce", utc=True).dt.tz_localize(None).dt.floor("D")
    data = data.dropna(subset=["day"]).groupby("day").agg(records=("records_count", "sum"), sessions=("session_id", "count")).reset_index()
    if data.empty:
        return None
    fig = go.Figure()
    fig.add_bar(x=data["day"], y=data["records"], name="Records", marker_color=PRIMARY,
                hovertemplate="%{x|%b %d}<br>Records: %{y}<extra></extra>")
    fig.add_scatter(x=data["day"], y=data["sessions"], name="Sessions", mode="lines+markers", yaxis="y2",
                    line={"color": ACCENT}, hovertemplate="%{x|%b %d}<br>Sessions: %{y}<extra></extra>")
    fig.update_layout(yaxis2={"overlaying": "y", "side": "right", "showgrid": False, "title": "Sessions"},
                      yaxis_title="Records")
    return _style(fig, "Scraping activity", height=300)
