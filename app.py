import streamlit as st

st.set_page_config(
    page_title="Cognita Attribution Dashboard",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="collapsed",
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

from data.synthetic import load_all_data
from utils.filters import render_sidebar
from pages import overview, conversion_matrix, opportunities, journeys, crm_journeys, search_terms, weekly_goals


@st.cache_data
def get_data():
    return load_all_data()


data = get_data()
filters = render_sidebar(data)

st.title("Cognita Attribution Dashboard")
st.caption("Position-based attribution (40/20/40) across GA4, Google Ads, Meta Ads, and Dynamics 365")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Overview",
    "Conversion Matrix",
    "Opportunities",
    "Journeys",
    "CRM Journeys",
    "Search Terms",
    "Weekly Goals",
])

with tab1:
    overview.render(data, filters)

with tab2:
    conversion_matrix.render(data, filters)

with tab3:
    opportunities.render(data, filters)

with tab4:
    journeys.render(data, filters)

with tab5:
    crm_journeys.render(data, filters)

with tab6:
    search_terms.render(data, filters)

with tab7:
    weekly_goals.render(data, filters)
