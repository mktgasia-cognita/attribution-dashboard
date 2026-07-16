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
    safe_tip = tip.replace('"', '&quot;')
    return (
        f' <span class="kpi-info" data-tip="{safe_tip}">&#8505;'
        f'<span class="kpi-tooltip">{safe_tip}</span></span>'
    )
