import streamlit as st

GUIDE_STYLE = (
    "background:#f0f7ff; border-left:3px solid #3498db; "
    "padding:10px 14px; margin:0 0 16px; border-radius:0 6px 6px 0; "
    "font-size:13px; color:#2c3e50; line-height:1.6;"
)


def section_guide(text):
    st.markdown(
        f'<div style="{GUIDE_STYLE}">{text}</div>',
        unsafe_allow_html=True,
    )


def info_icon(tip):
    return f' <span class="kpi-info" title="{tip}">&#8505;</span>'


INFO_ICON_CSS = """
.kpi-info {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px; height: 16px;
    border-radius: 50%;
    background: rgba(0,0,0,0.10);
    font-size: 10px;
    cursor: help;
    margin-left: 4px;
    vertical-align: middle;
    font-style: normal;
    transition: background 0.15s;
}
.kpi-info:hover { background: rgba(0,0,0,0.20); }
"""
