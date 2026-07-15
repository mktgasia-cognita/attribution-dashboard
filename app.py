import os
import streamlit as st
import streamlit_authenticator as stauth

st.set_page_config(
    page_title="Cognita Attribution Dashboard",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _authenticate():
    """Per-user auth with role-based school access via streamlit-authenticator."""
    try:
        credentials = st.secrets["credentials"]
        cookie = st.secrets["cookie"]
    except KeyError:
        return True, "cognita"

    creds_dict = {"usernames": {}}
    for uname, udata in credentials.get("usernames", {}).items():
        creds_dict["usernames"][uname] = {
            "email": str(udata.get("email", "")),
            "first_name": str(udata.get("first_name", "")),
            "last_name": str(udata.get("last_name", "")),
            "password": str(udata.get("password", "")),
            "roles": list(udata.get("roles", [])),
        }

    authenticator = stauth.Authenticate(
        creds_dict,
        cookie["name"],
        cookie["key"],
        cookie.get("expiry_days", 7),
    )

    if not st.session_state.get("authentication_status"):
        st.markdown("""
        <style>
            .stApp {background-color: #fafbfc;}
            section[data-testid="stSidebar"] {display: none;}
            header[data-testid="stHeader"] {display: none;}
            /* Centre and constrain login form width */
            [data-testid="stForm"] {
                max-width: 400px;
                margin: 0 auto;
            }
        </style>
        """, unsafe_allow_html=True)
        st.markdown("<div style='padding-top: 12vh;'></div>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center;'>Cognita Attribution Dashboard</h3>",
                    unsafe_allow_html=True)

    try:
        authenticator.login()
    except Exception as e:
        st.error(e)

    if st.session_state.get("authentication_status") is None:
        st.markdown("<p style='text-align:center; color:#888; font-size:0.85rem;'>"
                    "Contact your Cognita marketing team for login credentials.</p>",
                    unsafe_allow_html=True)

    if st.session_state.get("authentication_status"):
        authenticator.logout()
        username = st.session_state.get("username", "")
        name = st.session_state.get("name", "")
        user_info = creds_dict["usernames"].get(username, {})
        roles = user_info.get("roles", [])
        role = roles[0] if roles else "cognita"
        st.sidebar.caption(f"Signed in as {name}")
        return True, role

    if st.session_state.get("authentication_status") is False:
        st.error("Incorrect username or password")

    st.stop()


authenticated, user_role = _authenticate()

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
    /* Tablet: prevent KPI label truncation */
    @media (max-width: 768px) {
        .stMetric label { font-size: 0.75rem !important; }
        .stMetric [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    }
</style>
""", unsafe_allow_html=True)

from data.real_data import load_data
from utils.filters import render_sidebar
from views import overview, conversion_matrix, opportunities, journeys, crm_journeys, search_terms, weekly_goals


def _data_source():
    src = os.environ.get("DATA_SOURCE", "").lower()
    if src:
        return src
    try:
        return st.secrets.get("data_source", "csv").lower()
    except Exception:
        return "csv"


DATA_VERSION = "6"


@st.cache_data(ttl=3600 if _data_source() == "bigquery" else None)
def get_data(version=DATA_VERSION, source=None):
    # version + source are part of the cache key: bumping DATA_VERSION or
    # switching data source invalidates cached data (underscore-prefixed
    # params are excluded from Streamlit's cache key - do not rename back).
    if source == "bigquery":
        from data.bigquery import load_data_from_bq
        return load_data_from_bq()
    return load_data()


PAGES = {
    "Overview": overview,
    "Conversion Matrix": conversion_matrix,
    "Opportunities": opportunities,
    "Journeys": journeys,
    "CRM Journeys": crm_journeys,
    "Search Terms": search_terms,
    "Weekly Goals": weekly_goals,
}

page = st.sidebar.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")
st.sidebar.divider()

try:
    data = get_data(source=_data_source())
except Exception as exc:
    st.error(
        "Could not load dashboard data. If this is BigQuery mode, check the "
        "service account secrets on Streamlit Cloud, or set data_source = "
        "'csv' to use the bundled snapshot."
    )
    st.caption(f"Details: {type(exc).__name__}: {exc}")
    st.stop()

filters = render_sidebar(data, role=user_role)

st.title("BCS Attribution Dashboard")
dates = data["attributed"]["date"].dropna()
caption = "Markov attribution (per-stage, campaign-level) — D365 + BigQuery GA4"
if len(dates):
    caption += f" | {dates.min().strftime('%b %-d')}–{dates.max().strftime('%b %-d')}"
run_ts = data.get("bq_run_ts")
if run_ts:
    caption += f" | Live BQ (run {run_ts[:10]}); weekly goals + campaign names from repo files"
else:
    caption += " | Data refreshed weekly"
st.caption(caption)

PAGES[page].render(data, filters)
