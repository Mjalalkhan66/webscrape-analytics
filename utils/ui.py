"""Shared Streamlit UI helpers: theme CSS, headers and metric cards."""
from __future__ import annotations

import html

import streamlit as st

CSS = """
<style>
:root { --card-bg:#121A2E; --card-border:rgba(124,92,255,.25); --muted:#93A0BD; --accent:#22D3EE; --primary:#7C5CFF; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1250px; }
h1, h2, h3 { letter-spacing: -0.01em; }
.page-title { font-size: 2rem; font-weight: 700; margin: 0; }
.page-sub { color: var(--muted); margin: .15rem 0 1.4rem 0; }
.metric-card { background: linear-gradient(145deg,#141C33,#0F1628); border: 1px solid var(--card-border);
  border-radius: 14px; padding: 16px 18px; box-shadow: 0 6px 18px rgba(0,0,0,.28); height: 100%; }
.metric-label { color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }
.metric-value { font-size: 1.85rem; font-weight: 700; margin-top: 2px;
  background: linear-gradient(90deg,#fff,var(--accent)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.metric-help { color: var(--muted); font-size: .75rem; margin-top: 2px; }
.hero { background: radial-gradient(120% 140% at 0% 0%, rgba(124,92,255,.28), rgba(18,26,46,.9) 55%);
  border: 1px solid var(--card-border); border-radius: 18px; padding: 26px 28px; margin-bottom: 1.2rem; }
.hero h1 { margin: 0 0 .3rem 0; font-size: 2.2rem; }
.hero p { color: #C9D2E6; margin: 0; }
[data-testid="stSidebar"] { border-right: 1px solid rgba(255,255,255,.06); }
div[data-testid="stDataFrame"] { border: 1px solid rgba(255,255,255,.08); border-radius: 10px; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    inject_css()
    st.markdown(
        f'<p class="page-title">{html.escape(icon)} {html.escape(title)}</p>'
        f'<p class="page-sub">{html.escape(subtitle)}</p>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str | int | float, help_text: str = "") -> None:
    """Render a styled metric card. All inputs are HTML-escaped."""
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{html.escape(str(label))}</div>'
        f'<div class="metric-value">{html.escape(str(value))}</div>'
        f'<div class="metric-help">{html.escape(help_text)}</div></div>',
        unsafe_allow_html=True,
    )


def metric_row(items: list[tuple[str, str | int | float, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, help_text) in zip(cols, items):
        with col:
            metric_card(label, value, help_text)


def friendly_error(message: str) -> None:
    st.error(message, icon="🚫")
