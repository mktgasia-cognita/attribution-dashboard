import streamlit as st

st.set_page_config(
    page_title="Cognita Attribution Dashboard",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _check_password():
    if "password" not in st.secrets:
        return True
    if st.session_state.get("authenticated"):
        return True

    st.markdown("""
    <style>
        .stApp {background-color: #fafbfc;}
        section[data-testid="stSidebar"] {display: none;}
        header[data-testid="stHeader"] {display: none;}
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<div style='padding-top: 20vh;'></div>", unsafe_allow_html=True)
        st.markdown("#### Cognita Attribution Dashboard")
        pwd = st.text_input("Password", type="password", key="pwd_input")
        if pwd == st.secrets["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
        elif pwd:
            st.error("Incorrect password")
    return False


if not _check_password():
    st.stop()

st.markdown("""
<style>
    .stApp {background-color: #fafbfc;}
    section[data-testid="stSidebar"] {background-color: #ffffff; border-right: 1px solid #e0e0e0;}
    .stMetric {background-color: #ffffff; padding: 16px; border-radius: 8px;
               border: 1px solid #e8e8e8; box-shadow: 0 1px 3px rgba(0,0,0,0.05);}
    .stTabs [data-baseweb="tab-list"] {gap: 4px;}
    .stTabs [data-baseweb="tab"] {padding: 8px 20px; font-weight: 500;}
    /* Fix Plotly Sankey text: remove shadow/stroke, force solid black */
    .js-plotly-plot .sankey .node-label,
    .js-plotly-plot .sankey text,
    .js-plotly-plot g.sankey text {
        fill: #1a1a1a !important;
        stroke: none !important;
        stroke-width: 0 !important;
        text-shadow: none !important;
        paint-order: normal !important;
        font-family: Arial, Helvetica, sans-serif !important;
        font-size: 13px !important;
    }
    /* Push Plotly modebar above chart content */
    .js-plotly-plot .modebar-container {
        top: -40px !important;
        right: 0 !important;
    }
    .js-plotly-plot {
        overflow: visible !important;
    }
</style>
""", unsafe_allow_html=True)

from data.real_data import load_bcs_data
from utils.filters import render_sidebar
from views import overview, conversion_matrix, opportunities, journeys, crm_journeys, search_terms, weekly_goals


DATA_VERSION = "3"


@st.cache_data
def get_data(_version=DATA_VERSION):
    return load_bcs_data()


PAGES = {
    "Overview": overview,
    "Conversion Matrix": conversion_matrix,
    "Opportunities": opportunities,
    "Journeys": journeys,
    "CRM Journeys": crm_journeys,
    "Search Terms": search_terms,
    "Weekly Goals": weekly_goals,
}

page = st.sidebar.radio("", list(PAGES.keys()), label_visibility="collapsed")
st.sidebar.divider()

data = get_data()
filters = render_sidebar(data)

st.title("BCS Attribution Dashboard")
dates = data["attributed"]["date"].dropna()
if len(dates):
    date_min = dates.min().strftime("%b %-d")
    date_max = dates.max().strftime("%b %-d")
    st.caption(f"Markov attribution (per-stage, campaign-level) — D365 + BigQuery GA4 | {date_min}–{date_max}")
else:
    st.caption("Markov attribution (per-stage, campaign-level) — D365 + BigQuery GA4")

PAGES[page].render(data, filters)
