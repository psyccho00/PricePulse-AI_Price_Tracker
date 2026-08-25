import streamlit as st
import datetime
import time
import pandas as pd
import streamlit.components.v1 as components
from api_client import PriceTrackerAPIClient
from typing import Optional, Dict, Any, List
import json
import re
import ast
import textwrap

# ==========================================
# Page Configurations
# ==========================================
st.set_page_config(
    page_title="Smart Price Monitor - Shopping Intelligence Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize API Client
api_base_url = "http://localhost:8000"
client = PriceTrackerAPIClient(base_url=api_base_url)

# ==========================================
# Authentication & Session State Restoration
# ==========================================
# Remove any token from query params if legacy params exist
if "auth_token" in st.query_params:
    del st.query_params["auth_token"]

if "token" not in st.session_state:
    st.session_state["token"] = None
if "user" not in st.session_state:
    st.session_state["user"] = None
if "user_profile" not in st.session_state:
    st.session_state["user_profile"] = None
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "auth_page" not in st.session_state:
    st.session_state["auth_page"] = "login"
if "nav_section" not in st.session_state:
    st.session_state["nav_section"] = "📦 Tracked Products"
if "status_filter" not in st.session_state:
    st.session_state["status_filter"] = "All Products"

# Sync client token and verify authentication status
if st.session_state["token"]:
    client.token = st.session_state["token"]
    st.session_state["authenticated"] = True

    if st.session_state["user_profile"] is None:
        profile = client.get_profile()
        if profile is not None and isinstance(profile, dict):
            if profile.get("_auth_error") == "unauthorized":
                st.session_state["token"] = None
                st.session_state["user_profile"] = None
                st.session_state["user"] = None
                st.session_state["authenticated"] = False
                st.session_state["auth_page"] = "login"
                st.session_state["products"] = None
                st.session_state["alerts"] = None
                st.warning("Session expired or invalid. Please sign in again.")
                time.sleep(1)
                st.rerun()
            elif profile.get("_auth_error") != "offline":
                st.session_state["user_profile"] = profile
                st.session_state["user"] = profile

def perform_logout():
    """Completely clear authentication and user-specific session state."""
    client.logout()
    st.session_state["token"] = None
    st.session_state["user_profile"] = None
    st.session_state["user"] = None
    st.session_state["authenticated"] = False
    st.session_state["products"] = None
    st.session_state["alerts"] = None
    st.session_state["auth_page"] = "login"
    st.rerun()

# ==========================================
# Injected Premium SaaS CSS Design System
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&display=swap');

html, body, [class*="css"], .stMarkdown, .stText, p, div, h1, h2, h3, h4, h5, h6, button, input, textarea, select {
    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Base Canvas Background */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: #080A0F !important;
    color: #E8EAF0 !important;
}

/* Hide Default Streamlit Chrome */
header[data-testid="stHeader"], #MainMenu, footer, .stDeployButton {
    display: none !important;
}

/* Main Block Padding */
.main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 3rem !important;
    max-width: 1500px !important;
}

/* Typography Overrides */
p, .stMarkdown {
    color: #94A3B8 !important;
}
h1, h2, h3, h4, h5, h6 {
    color: #E8EAF0 !important;
}

/* ========================================= */
/* Streamlit Widget Overrides                */
/* ========================================= */

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0D1018 !important;
    border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
    padding-top: 1rem !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0.35rem !important;
}

/* Sidebar Nav Item Buttons */
[data-testid="stSidebar"] .stButton > button {
    width: 100% !important;
    background-color: transparent !important;
    color: #94A3B8 !important;
    border: 1px solid transparent !important;
    border-radius: 10px !important;
    padding: 8px 14px !important;
    font-weight: 500 !important;
    font-size: 13.5px !important;
    text-align: left !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    transition: all 0.2s ease !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: rgba(255, 255, 255, 0.04) !important;
    color: #E2E8F0 !important;
    border-color: transparent !important;
}
[data-testid="stSidebar"] .stButton > button:focus,
[data-testid="stSidebar"] .stButton > button:active {
    background-color: rgba(124, 58, 237, 0.12) !important;
    color: #C084FC !important;
    border: 1px solid rgba(139, 92, 246, 0.35) !important;
    box-shadow: 0 0 10px rgba(124, 58, 237, 0.1) !important;
}

/* Premium Sidebar Upgrade Card */
.sidebar-plan-card {
    background: linear-gradient(145deg, rgba(124,58,237,0.14), rgba(168,85,247,0.05));
    border: 1px solid rgba(139, 92, 246, 0.35);
    border-radius: 16px;
    padding: 16px;
    margin-top: 20px;
    margin-bottom: 10px;
}

/* Inputs & Form Controls Override */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-baseweb="input"],
[data-baseweb="textarea"] {
    background-color: #111522 !important;
    color: #E8EAF0 !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    caret-color: #7C3AED !important;
}
[data-baseweb="input"] {
    background-color: #111522 !important;
}
div[data-baseweb="base-input"] {
    background-color: transparent !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-baseweb="input"]:focus-within {
    border-color: rgba(139, 92, 246, 0.6) !important;
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.10) !important;
}
/* Change placeholder color */
[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-baseweb="input"] input::placeholder {
    color: #64748B !important;
}

/* Buttons */
[data-testid="stButton"] button {
    background-color: #151A28 !important;
    color: #E8EAF0 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}
[data-testid="stButton"] button:hover {
    border-color: rgba(139, 92, 246, 0.35) !important;
    background-color: rgba(124, 58, 237, 0.12) !important;
    color: #F1F5F9 !important;
}
/* Primary Button */
[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #7C3AED, #A855F7) !important;
    border: none !important;
    color: #ffffff !important;
    font-weight: 600 !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4) !important;
    background: linear-gradient(135deg, #8B5CF6, #C084FC) !important;
}

/* Popover & Selectbox dropdown */
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[data-testid="stPopoverBody"] {
    background-color: #111521 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-shadow: 0 20px 50px rgba(0,0,0,0.45) !important;
    border-radius: 12px !important;
}
[data-baseweb="menu"] li {
    color: #E8EAF0 !important;
}
[data-baseweb="menu"] li:hover {
    background-color: rgba(124, 58, 237, 0.12) !important;
}
/* Popover Trigger Button */
[data-testid="stPopover"] > button {
    background-color: #151A28 !important;
    color: #E8EAF0 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
}
/* Allow popover hover styling */
[data-testid="stPopover"] > button:hover {
    border-color: rgba(139, 92, 246, 0.35) !important;
    background-color: rgba(124, 58, 237, 0.12) !important;
}

/* Selectbox */
[data-baseweb="select"] > div {
    background-color: #111522 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    color: #E8EAF0 !important;
}

/* Checkbox */
[data-testid="stCheckbox"] label div[data-testid="stMarkdownContainer"] {
    color: #94A3B8 !important;
}
[data-baseweb="checkbox"] > div:first-child {
    background-color: #111522 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
}

/* Custom Streamlit Tabs Styling */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background-color: rgba(17, 21, 33, 0.8) !important;
    border-radius: 14px !important;
    padding: 4px !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    gap: 4px !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    height: 42px !important;
    border-radius: 10px !important;
    color: #94A3B8 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    border: none !important;
    padding: 0 20px !important;
    background-color: transparent !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background-color: transparent !important;
    color: #C084FC !important;
    border-bottom: 2px solid #7C3AED !important;
    border-radius: 0px !important;
}

/* ========================================= */
/* Custom Components                         */
/* ========================================= */

/* Split Screen Hero Container for Auth */
.split-hero-container {
    display: flex;
    min-height: 82vh;
    border-radius: 24px;
    overflow: hidden;
    background: #111521;
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(20px);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6);
    margin: 10px auto;
}

/* Portfolio Metric Cards */
.portfolio-card {
    background: #111521;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    height: 100%;
}
.portfolio-card:hover {
    border-color: rgba(139, 92, 246, 0.35);
    transform: translateY(-2px);
    box-shadow: 0 12px 30px rgba(124, 58, 237, 0.10);
}

.metric-label {
    color: #94A3B8;
    font-size: 11.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
.metric-value {
    font-size: 28px;
    font-weight: 700;
    margin-top: 6px;
    letter-spacing: -0.5px;
    color: #E8EAF0;
}
.metric-sub {
    font-size: 12px;
    color: #64748B;
    margin-top: 4px;
    font-weight: 500;
}

/* Product Cards */
.product-card {
    background: #111521;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 22px;
    margin-bottom: 20px;
    transition: all 0.25s ease;
}
.product-card:hover {
    border-color: rgba(139, 92, 246, 0.35);
    box-shadow: 0 14px 44px rgba(124, 58, 237, 0.08);
}

/* Product Image Box */
.product-img-box {
    width: 100%;
    aspect-ratio: 1/1;
    max-height: 180px;
    background: #0D1018;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.06);
    padding: 10px;
}
.product-img-box img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}
.watchlist-heart-icon {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: rgba(17, 21, 33, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #94A3B8;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s ease;
}
.watchlist-heart-icon:hover {
    color: #EF4565;
    background: rgba(239, 69, 101, 0.15);
}

/* Store Badges */
.badge {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: white;
}
.badge-amazon { background-color: #E47911; }
.badge-flipkart { background-color: #2874F0; }
.badge-myntra { background-color: #FF3F6C; }
.badge-unknown { background-color: #64748B; }

/* Status Pills */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.status-pill-ready { background-color: rgba(34, 197, 94, 0.15); color: #22C55E; border: 1px solid rgba(34, 197, 94, 0.3); }
.status-pill-near { background-color: rgba(245, 158, 11, 0.15); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.3); }
.status-pill-above { background-color: rgba(239, 69, 101, 0.15); color: #EF4565; border: 1px solid rgba(239, 69, 101, 0.3); }

/* Shimmer Skeleton Loaders */
@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
.skeleton-card {
    background: #111521;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
}
.shimmer {
    background: linear-gradient(90deg, #151A28 25%, #1A2133 50%, #151A28 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 8px;
}
.skeleton-image { height: 150px; width: 100%; margin-bottom: 16px; }
.skeleton-title { height: 24px; width: 70%; margin-bottom: 12px; }
.skeleton-text { height: 14px; width: 90%; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# Data Sanitization Helpers
# ==========================================
def clean_scraped_title(title: Any) -> str:
    if not title:
        return "Tracked Product"
    title_str = str(title).strip()
    if " - " in title_str and (title_str.startswith("{") or "'name':" in title_str or "'uidx':" in title_str):
        parts = title_str.split(" - ", 1)
        if len(parts) > 1 and not parts[1].strip().startswith("{"):
            title_str = parts[1].strip()
    if title_str.startswith("{") or title_str.startswith("["):
        try:
            parsed = json.loads(title_str.replace("'", '"'))
            if isinstance(parsed, dict) and "name" in parsed:
                return parsed["name"]
        except Exception:
            pass
    title_str = re.sub(r"\{[^{}]*\}", "", title_str)
    title_str = re.sub(r"<[^>]+>", "", title_str).replace("  ", " ").strip(" -:;")
    return title_str or "Tracked Product"

def clean_scraped_image_url(url: Any) -> Optional[str]:
    if not url:
        return None
    if isinstance(url, dict):
        for key in ["url", "src", "image", "imageUrl", "large"]:
            val = url.get(key)
            if val:
                cleaned = clean_scraped_image_url(val)
                if cleaned:
                    return cleaned
        return None
    if isinstance(url, list):
        return clean_scraped_image_url(url[0]) if url else None
    url_str = str(url).strip()
    if url_str.startswith("{") or url_str.startswith("["):
        try:
            return clean_scraped_image_url(json.loads(url_str))
        except Exception:
            pass
    url_str = re.sub(r"<[^>]+>", "", url_str).strip("'\"[]() ")
    return url_str if (url_str.startswith("http://") or url_str.startswith("https://")) else None

def relative_time(dt_val) -> str:
    if not dt_val:
        return "Never"
    try:
        if isinstance(dt_val, str):
            dt = datetime.datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        else:
            dt = dt_val
        now = datetime.datetime.now(datetime.timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return "Just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{int(minutes)}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{int(hours)}h ago"
        days = hours // 24
        return f"{int(days)}d ago"
    except Exception:
        return str(dt_val)

def get_product_image_html(image_url, name):
    clean_img = clean_scraped_image_url(image_url)
    clean_name = clean_scraped_title(name)
    heart_html = """<div class="watchlist-heart-icon" title="Add to Watchlist">♡</div>"""
    if clean_img:
        return textwrap.dedent(f"""
        <div class="product-img-box">
            {heart_html}
            <img src="{clean_img}" alt="{clean_name}" onerror="this.onerror=null; this.style.display='none'; this.nextElementSibling.style.display='block';">
            <svg style="display:none;" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#6C63FF" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <path d="M16 10a4 4 0 0 1-8 0"></path>
            </svg>
        </div>
        """).strip()
    else:
        return textwrap.dedent(f"""
        <div class="product-img-box">
            {heart_html}
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#6C63FF" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <path d="M16 10a4 4 0 0 1-8 0"></path>
            </svg>
        </div>
        """).strip()

def generate_sparkline_svg(history_prices: List[float]) -> str:
    """Generate inline SVG mini price trend sparkline chart matching reference."""
    if not history_prices or len(history_prices) == 0:
        history_prices = [10000, 9800, 9600, 9600]
    if len(history_prices) == 1:
        p = history_prices[0]
        history_prices = [p * 1.08, p * 1.04, p * 1.01, p, p]
    
    min_p = min(history_prices)
    max_p = max(history_prices)
    range_p = max_p - min_p if max_p != min_p else 1.0
    
    width = 170
    height = 42
    padding = 4
    
    pts = []
    n = len(history_prices)
    for i, p in enumerate(history_prices):
        x = padding + (i / (n - 1 if n > 1 else 1)) * (width - 2 * padding)
        y = height - padding - ((p - min_p) / range_p) * (height - 2 * padding)
        pts.append(f"{x:.1f},{y:.1f}")
    
    polyline_points = " ".join(pts)
    
    return textwrap.dedent(f"""
    <div style="background: rgba(14, 17, 26, 0.6); padding: 8px 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.06); width: 100%;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
            <span style="font-size: 10.5px; font-weight: 700; color: #94A3B8;">Price Trend (All Time)</span>
        </div>
        <svg width="100%" height="38" viewBox="0 0 170 42" style="overflow: visible;">
            <defs>
                <linearGradient id="spark-grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#6C63FF" stop-opacity="0.35"/>
                    <stop offset="100%" stop-color="#6C63FF" stop-opacity="0.0"/>
                </linearGradient>
            </defs>
            <polygon points="4,38 {polyline_points} 166,38" fill="url(#spark-grad)" />
            <polyline points="{polyline_points}" fill="none" stroke="#6C63FF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div style="display: flex; justify-content: space-between; font-size: 9px; color: #64748B;">
            <span>Mar</span>
            <span>Apr</span>
            <span>May</span>
            <span>Jun</span>
        </div>
    </div>
    """).strip()

def render_deal_score_ring(score: int = 72, status: str = "GOOD"):
    score_val = max(0, min(100, score))
    deg = int(score_val * 3.6)
    if score_val >= 70:
        color = "#2CB67D"
        label_text = "GREAT" if score_val >= 85 else "GOOD"
        exp_text = f"Price is {100 - score_val:.1f}% below avg"
    elif score_val >= 40:
        color = "#FF8C00"
        label_text = "TYPICAL"
        exp_text = "Near average market price"
    else:
        color = "#EF4565"
        label_text = "HIGH PRICE"
        exp_text = "Price is above average"

    return textwrap.dedent(f"""
    <div style="display: flex; align-items: center; gap: 10px;">
        <div style="position: relative; width: 44px; height: 44px; border-radius: 50%; background: conic-gradient({color} {deg}deg, #242A3E 0deg); display: flex; align-items: center; justify-content: center; shrink: 0;">
            <div style="width: 34px; height: 34px; border-radius: 50%; background: #121624; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; color: #FFF;">
                {score_val}
            </div>
        </div>
        <div>
            <div style="font-size: 10px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">Deal Score</div>
            <div style="font-size: 13px; font-weight: 800; color: {color};">{label_text}</div>
            <div style="font-size: 9.5px; color: #64748B;">{exp_text}</div>
        </div>
    </div>
    """).strip()

def render_skeleton_loaders():
    col1, col2 = st.columns(2)
    for col in [col1, col2]:
        with col:
            st.markdown(textwrap.dedent("""
            <div class="skeleton-card">
                <div class="shimmer skeleton-image"></div>
                <div class="shimmer skeleton-title"></div>
                <div class="shimmer skeleton-text"></div>
                <div class="shimmer skeleton-text" style="width: 50%;"></div>
            </div>
            """).strip(), unsafe_allow_html=True)

# ==========================================
# RENDER SCREEN FLOWS
# ==========================================

# ------------------------------------------
# 1. UNAUTHENTICATED FLOW (SPLIT HERO LOGIN PAGE)
# ------------------------------------------
if not st.session_state["token"]:
    col_hero_left, col_hero_right = st.columns([1, 1])

    with col_hero_left:
        st.markdown("""<div style="padding: 48px; background: linear-gradient(135deg, rgba(108, 99, 255, 0.18) 0%, rgba(139, 92, 246, 0.05) 50%, rgba(10, 12, 16, 0.95) 100%); border-radius: 24px; border: 1px solid rgba(255,255,255,0.08); height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
<div>
<div style="font-size: 46px; margin-bottom: 12px;">🎯</div>
<h1 style="font-size: 34px; font-weight: 900; color: #FFF; margin: 0; letter-spacing: -0.5px;">Smart Price Monitor</h1>
<p style="font-size: 15px; color: #94A3B8; font-weight: 500; margin-top: 8px;">
Intelligent price tracking & shopping optimization across 
<span style="color: #E47911; font-weight: 700;">Amazon</span>, 
<span style="color: #2874F0; font-weight: 700;">Flipkart</span> & 
<span style="color: #FF3F6C; font-weight: 700;">Myntra</span>
</p>
<hr style="border-color: rgba(255,255,255,0.08); margin: 28px 0;">
<div style="display: flex; flex-direction: column; gap: 14px; font-size: 14.5px; color: #CBD5E1; font-weight: 500;">
<div>✨ Real-time cross-store price comparison & arbitrage</div>
<div>🤖 Explainable AI Buy Score & Deal Score intelligence</div>
<div>🔔 Instant Email & WhatsApp threshold alerts</div>
<div>💳 Payment method & bank offer optimizer</div>
</div>
</div>
<div style="display: flex; gap: 18px; margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.08); font-size: 12px; color: #64748B; font-weight: 600;">
<span>🔒 Secure & Private</span>
<span>⚡ Real-time Tracking</span>
<span>🤖 AI Powered Insights</span>
</div>
</div>""", unsafe_allow_html=True)

    with col_hero_right:
        st.markdown("<div style='padding: 20px 30px;'>", unsafe_allow_html=True)
        
        # 1. Login Screen
        if st.session_state["auth_page"] == "login":
            st.markdown("""
            <h2 style="font-size: 28px; font-weight: 800; color: #FFF; margin-bottom: 4px;">Welcome Back 👋</h2>
            <p style="font-size: 14px; color: #94A3B8; margin-bottom: 28px;">Sign in to continue to your dashboard</p>
            """, unsafe_allow_html=True)
            
            with st.form("login_form"):
                email = st.text_input("Email Address", placeholder="e.g. name@example.com")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                remember = st.checkbox("Remember me for 30 days", value=True)
                submit = st.form_submit_button("🔑 Sign In to Dashboard", type="primary", use_container_width=True)
                
                if submit:
                    if not email or not password:
                        st.error("Please fill in all fields.")
                    else:
                        with st.spinner("Authenticating..."):
                            if client.login(email, password):
                                st.session_state["token"] = client.token
                                st.session_state["user_profile"] = client.get_profile()
                                st.session_state["user"] = st.session_state["user_profile"]
                                st.session_state["authenticated"] = True
                                st.session_state["products"] = None
                                st.session_state["alerts"] = None
                                st.rerun()
                            else:
                                st.error("Incorrect email or password.")
                                
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                if st.button("Create Account 👤", use_container_width=True):
                    st.session_state["auth_page"] = "signup"
                    st.rerun()
            with col_l2:
                if st.button("Forgot Password? ❓", use_container_width=True):
                    st.session_state["auth_page"] = "forgot"
                    st.rerun()

        # 2. Signup Screen
        elif st.session_state["auth_page"] == "signup":
            st.markdown("""
            <h2 style="font-size: 28px; font-weight: 800; color: #FFF; margin-bottom: 4px;">Create Account 👤</h2>
            <p style="font-size: 14px; color: #94A3B8; margin-bottom: 28px;">Get started tracking your favorite products</p>
            """, unsafe_allow_html=True)
            
            with st.form("signup_form"):
                name = st.text_input("Full Name", placeholder="e.g. John Doe")
                email = st.text_input("Email Address", placeholder="e.g. name@example.com")
                password = st.text_input("Password (Min 8 chars)", type="password", placeholder="Create password")
                submit = st.form_submit_button("Sign Up & Register", type="primary", use_container_width=True)
                
                if submit:
                    if not name or not email or not password:
                        st.error("Please fill in all fields.")
                    elif len(password) < 8:
                        st.error("Password must be at least 8 characters long.")
                    else:
                        with st.spinner("Creating account..."):
                            res = client.register(name, email, password)
                            if res:
                                st.success("Account created successfully! Please sign in.")
                                st.session_state["auth_page"] = "login"
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("A user with this email address already exists.")
                                
            if st.button("Back to Sign In 🔑", use_container_width=True):
                st.session_state["auth_page"] = "login"
                st.rerun()

        # 3. Forgot Password Screen
        elif st.session_state["auth_page"] == "forgot":
            st.markdown("""
            <h2 style="font-size: 28px; font-weight: 800; color: #FFF; margin-bottom: 4px;">Reset Password 🔑</h2>
            <p style="font-size: 14px; color: #94A3B8; margin-bottom: 28px;">Generate your secure access token</p>
            """, unsafe_allow_html=True)
            
            if "reset_token_sent" not in st.session_state:
                st.session_state["reset_token_sent"] = False
                
            if not st.session_state["reset_token_sent"]:
                with st.form("forgot_form"):
                    email = st.text_input("Email Address", placeholder="e.g. name@example.com")
                    submit = st.form_submit_button("Generate Reset Token", type="primary", use_container_width=True)
                    
                    if submit:
                        if not email:
                            st.error("Email is required.")
                        else:
                            with st.spinner("Generating reset token..."):
                                res = client.forgot_password(email)
                                if res:
                                    st.session_state["reset_token_val"] = res.get("token")
                                    st.session_state["reset_token_sent"] = True
                                    st.success("Reset token generated!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to generate token.")
            else:
                st.info(f"🔑 **Reset token:** `{st.session_state.get('reset_token_val')}`")
                with st.form("reset_pw_form"):
                    token = st.text_input("Reset Token", value=st.session_state.get("reset_token_val", ""))
                    new_pw = st.text_input("New Password (Min 8 chars)", type="password", placeholder="Enter new password")
                    submit = st.form_submit_button("Set New Password", type="primary", use_container_width=True)
                    
                    if submit:
                        if not token or not new_pw:
                            st.error("All fields are required.")
                        elif len(new_pw) < 8:
                            st.error("Password must be at least 8 characters long.")
                        else:
                            with st.spinner("Resetting password..."):
                                if client.reset_password(token, new_pw):
                                    st.success("Password updated! Please sign in.")
                                    st.session_state["reset_token_sent"] = False
                                    st.session_state["auth_page"] = "login"
                                    time.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.error("Invalid reset token.")
                                    
                if st.button("Cancel & Go Back", use_container_width=True):
                    st.session_state["reset_token_sent"] = False
                    st.session_state["auth_page"] = "login"
                    st.rerun()
                    
            if not st.session_state["reset_token_sent"]:
                if st.button("Back to Sign In 🔑", use_container_width=True):
                    st.session_state["auth_page"] = "login"
                    st.rerun()
                    
        st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------
# 2. AUTHENTICATED SaaS DASHBOARD FLOW
# ------------------------------------------
else:
    is_healthy = client.check_health()
    user_profile = st.session_state.get("user_profile") or {}
    user_name = user_profile.get("name") or "User"
    user_email = user_profile.get("email") or ""

    # ==========================================
    # SIDEBAR NAVIGATION (PERSISTENT LEFT SHELL)
    # ==========================================
    with st.sidebar:
        st.markdown(textwrap.dedent("""
        <div style="display: flex; align-items: center; gap: 10px; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 12px;">
            <span style="font-size: 26px;">🎯</span>
            <div>
                <div style="font-weight: 800; font-size: 16px; color: #FFF; letter-spacing: -0.3px;">Smart Price Monitor</div>
                <div style="font-size: 11px; color: #64748B;">Intelligent price tracking</div>
            </div>
        </div>
        """).strip(), unsafe_allow_html=True)

        st.markdown("<p style='color: #64748B; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin: 12px 0 4px 0;'>MAIN</p>", unsafe_allow_html=True)
        if st.button("🏠  Overview", key="sb_nav_overview", use_container_width=True):
            st.session_state["nav_section"] = "📦 Tracked Products"
            st.rerun()
        if st.button("📦  Tracked Products", key="sb_nav_products", use_container_width=True):
            st.session_state["nav_section"] = "📦 Tracked Products"
            st.rerun()
        if st.button("🛍  Shopping Insights", key="sb_nav_insights", use_container_width=True):
            st.session_state["nav_section"] = "🛍 Shopping Insights"
            st.rerun()
        if st.button("📈  Price History", key="sb_nav_history", use_container_width=True):
            st.session_state["nav_section"] = "📦 Tracked Products"
            st.toast("Price history charts are available in product details.")
            st.rerun()
        if st.button("🤖  AI Insights  ✨", key="sb_nav_ai", use_container_width=True):
            st.session_state["nav_section"] = "🛍 Shopping Insights"
            st.rerun()
        if st.button("🔔  Price Alerts", key="sb_nav_alerts", use_container_width=True):
            st.session_state["nav_section"] = "📦 Tracked Products"
            st.rerun()

        st.markdown("<p style='color: #64748B; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin: 16px 0 4px 0;'>TOOLS</p>", unsafe_allow_html=True)
        if st.button("⚖️  Price Comparison", key="sb_nav_comp", use_container_width=True):
            st.session_state["nav_section"] = "📦 Tracked Products"
            st.toast("Cross-store comparison active in catalog.")
            st.rerun()
        if st.button("💳  Payment Optimizer", key="sb_nav_pay", use_container_width=True):
            st.session_state["nav_section"] = "📦 Tracked Products"
            st.toast("Payment Optimizer enabled.")
            st.rerun()
        if st.button("🔌  Browser Extension", key="sb_nav_ext", use_container_width=True):
            st.toast("Browser Extension is available via web store!")

        st.markdown("<p style='color: #64748B; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin: 16px 0 4px 0;'>ACCOUNT</p>", unsafe_allow_html=True)
        if st.button("⚙️  Account Settings", key="sb_nav_settings", use_container_width=True):
            st.session_state["nav_section"] = "⚙ Account Settings"
            st.rerun()

        st.markdown(textwrap.dedent("""
        <div class="sidebar-plan-card">
            <div style="font-size: 13px; font-weight: 800; color: #FFF;">🚀 Premium Plan</div>
            <div style="font-size: 11px; color: #94A3B8; margin-top: 4px; line-height: 1.4;">Unlock advanced AI insights, price forecasts & more.</div>
        </div>
        """).strip(), unsafe_allow_html=True)
        if st.button("Upgrade Now", key="side_upgrade_btn", type="primary", use_container_width=True):
            st.toast("You are already on the Unlimited Plan!")

    # ==========================================
    # TOP HEADER & PROFILE DROPDOWN MENU
    # ==========================================
    col_top_search, col_top_actions = st.columns([7, 3])
    
    with col_top_search:
        st.text_input("Search", placeholder="🔍  Search products, categories or stores...                                                    ⌘K", label_visibility="collapsed", key="global_search_input")
        
    with col_top_actions:
        r_col1, r_col2, r_col3 = st.columns([1, 1, 4])
        with r_col1:
            st.button("🌙", key="theme_toggle_btn", help="Toggle Theme", use_container_width=True)
        with r_col2:
            st.button("🔔", key="notif_bell_btn", help="Notifications", use_container_width=True)
        with r_col3:
            initial = user_name[0].upper() if user_name else "U"
            with st.popover(f"👤 {user_name} ▾", use_container_width=True):
                st.markdown(f"**{user_name}**")
                st.caption(user_email)
                st.caption("✨ Premium Plan")
                st.markdown("---")
                if st.button("⚙️  Profile Settings", key="pop_prof_btn", use_container_width=True):
                    st.session_state["nav_section"] = "⚙ Account Settings"
                    st.rerun()
                if st.button("💳  Billing & Subscription", key="pop_bill_btn", use_container_width=True):
                    st.toast("Subscription Active: Unlimited Tier")
                if st.button("🔔  Notification Preferences", key="pop_notif_pref", use_container_width=True):
                    st.toast("Email & WhatsApp active")
                if st.button("🔒  Security", key="pop_sec_btn", use_container_width=True):
                    st.session_state["nav_section"] = "⚙ Account Settings"
                    st.rerun()
                if st.button("❓  Help & Support", key="pop_help_btn", use_container_width=True):
                    st.toast("Contact support@smartpricemonitor.com")
                st.markdown("---")
                if st.button("🚪  Log out", key="pop_logout_act_btn", use_container_width=True):
                    perform_logout()

    # ==========================================
    # WELCOME HERO SECTION
    # ==========================================
    sched_status = client.get_scheduler_status() if is_healthy else None
    last_run = sched_status.get("last_run") if sched_status else None
    updated_str = relative_time(last_run)

    st.markdown(textwrap.dedent(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin: 14px 0 20px 0;">
        <div>
            <h1 style="font-size: 26px; font-weight: 900; color: #FFF; margin: 0; letter-spacing: -0.5px;">Welcome back, {user_name}! 👋</h1>
            <p style="font-size: 13.5px; color: #94A3B8; margin: 2px 0 0 0;">Here's what's happening with your portfolio today.</p>
        </div>
        <div>
            <span style="display: inline-flex; align-items: center; gap: 6px; background: rgba(44, 182, 125, 0.12); border: 1px solid rgba(44, 182, 125, 0.3); color: #2CB67D; padding: 6px 14px; border-radius: 20px; font-size: 12.5px; font-weight: 700;">
                <span style="height: 8px; width: 8px; background-color: #2CB67D; border-radius: 50%; display: inline-block;"></span>
                Live • Updated {updated_str}
            </span>
        </div>
    </div>
    """).strip(), unsafe_allow_html=True)

    # Fetch active products & alerts
    if "products" not in st.session_state or st.session_state["products"] is None:
        skeleton_box = st.empty()
        with skeleton_box.container():
            render_skeleton_loaders()
        st.session_state["products"] = client.get_products()
        skeleton_box.empty()
    products = st.session_state["products"] or []

    if "alerts" not in st.session_state or st.session_state["alerts"] is None:
        st.session_state["alerts"] = client.get_alerts()
    all_alerts = st.session_state["alerts"] or []

    # Calculate dynamic portfolio metrics
    target_prices = {}
    product_alerts = {}
    for a in all_alerts:
        target_prices[a["product_id"]] = a["target_price"]
        product_alerts.setdefault(a["product_id"], []).append(a)

    total_products = len(products)
    total_portfolio_value = 0.0
    total_target_budget = 0.0
    products_ready_to_buy = 0
    products_above_target = 0

    for p in products:
        links = p.get("links", [])
        active_links = [l for l in links if l.get("is_active", True)]
        active_prices = [l["current_price"] for l in active_links if l.get("current_price") is not None]
        current_price = min(active_prices) if active_prices else None
        target_price = target_prices.get(p["id"], None)

        if current_price is not None:
            total_portfolio_value += current_price
        if target_price is not None:
            total_target_budget += target_price

        if current_price is not None and target_price is not None:
            if current_price <= target_price:
                products_ready_to_buy += 1
            else:
                products_above_target += 1

    potential_savings = max(0.0, total_portfolio_value - total_target_budget)

    # ==========================================
    # 5 DASHBOARD METRIC CARDS ROW
    # ==========================================
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(textwrap.dedent(f"""
        <div class="portfolio-card">
            <div class="metric-label">Tracked Products</div>
            <div class="metric-value" style="color: #6C63FF;">{total_products:02d}</div>
            <div class="metric-sub">Active items being watched</div>
            <div style="font-size: 11px; color: #2CB67D; font-weight: 700; margin-top: 6px;">↑ 0 this week</div>
        </div>
        """).strip(), unsafe_allow_html=True)
    with m2:
        st.markdown(textwrap.dedent(f"""
        <div class="portfolio-card">
            <div class="metric-label">Total Portfolio Value</div>
            <div class="metric-value" style="color: #2CB67D;">₹{total_portfolio_value:,.2f}</div>
            <div class="metric-sub">Current lowest market price</div>
        </div>
        """).strip(), unsafe_allow_html=True)
    with m3:
        st.markdown(textwrap.dedent(f"""
        <div class="portfolio-card">
            <div class="metric-label">Total Target Budget</div>
            <div class="metric-value" style="color: #E47911;">₹{total_target_budget:,.2f}</div>
            <div class="metric-sub">Configured target sum</div>
        </div>
        """).strip(), unsafe_allow_html=True)
    with m4:
        st.markdown(textwrap.dedent(f"""
        <div class="portfolio-card">
            <div class="metric-label">Potential Savings</div>
            <div class="metric-value" style="color: #EF4565;">₹{potential_savings:,.2f}</div>
            <div class="metric-sub">Difference to reach target</div>
        </div>
        """).strip(), unsafe_allow_html=True)
    with m5:
        st.markdown(textwrap.dedent(f"""
        <div class="portfolio-card">
            <div class="metric-label">Status Counts</div>
            <div style="font-size: 13px; font-weight: 800; color: #FFF; margin-top: 6px;">
                <span style="color: #2CB67D;">🟢 Ready: {products_ready_to_buy}</span><br>
                <span style="color: #EF4565;">🔴 Above: {products_above_target}</span>
            </div>
            <div class="metric-sub">Buy readiness split</div>
        </div>
        """).strip(), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # SUB-NAV TABS & FILTER BAR
    # ==========================================
    tabs_list = ["Tracked Products Catalog", "Shopping Insights", "+ Add Product Tracking", "Account Settings"]
    tab_catalog, tab_insights, tab_add, tab_settings = st.tabs(tabs_list)

    # ------------------------------------------
    # TAB 1: TRACKED PRODUCTS CATALOG
    # ------------------------------------------
    with tab_catalog:
        # Filter chips row
        f_col1, f_col2 = st.columns([8, 2])
        with f_col1:
            st.markdown(textwrap.dedent(f"""
            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 16px;">
                <span style="background: #6C63FF; color: #FFF; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700;">All Products ({total_products})</span>
                <span style="background: rgba(18,22,34,0.8); color: #94A3B8; border: 1px solid rgba(255,255,255,0.08); padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600;">Price Drops (0)</span>
                <span style="background: rgba(18,22,34,0.8); color: #94A3B8; border: 1px solid rgba(255,255,255,0.08); padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600;">Near Target ({products_ready_to_buy})</span>
                <span style="background: rgba(18,22,34,0.8); color: #94A3B8; border: 1px solid rgba(255,255,255,0.08); padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600;">Out of Stock (0)</span>
                <span style="background: rgba(18,22,34,0.8); color: #94A3B8; border: 1px solid rgba(255,255,255,0.08); padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600;">Watchlist (0)</span>
            </div>
            """).strip(), unsafe_allow_html=True)
        with f_col2:
            st.markdown(textwrap.dedent("""
            <div style="display: flex; gap: 8px; justify-content: flex-end; align-items: center;">
                <span style="background: rgba(18,22,34,0.8); color: #FFF; border: 1px solid rgba(255,255,255,0.08); padding: 6px 10px; border-radius: 8px; font-size: 13px;">⊞</span>
                <span style="background: rgba(18,22,34,0.8); color: #94A3B8; border: 1px solid rgba(255,255,255,0.08); padding: 6px 10px; border-radius: 8px; font-size: 13px;">☰</span>
                <span style="background: rgba(18,22,34,0.8); color: #94A3B8; border: 1px solid rgba(255,255,255,0.08); padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;">⚡ Filters</span>
            </div>
            """).strip(), unsafe_allow_html=True)

        if not products:
            st.markdown(textwrap.dedent("""
            <div style="text-align: center; padding: 48px; background: rgba(18,22,34,0.5); border-radius: 20px; border: 1px dashed rgba(255,255,255,0.1);">
                <div style="font-size: 42px;">🛍️</div>
                <h3 style="color: #FFF; font-weight: 800; margin-top: 8px;">No Tracked Products Registered</h3>
                <p style="color: #94A3B8; font-size: 14px;">Switch to '+ Add Product Tracking' tab to monitor your first product link!</p>
            </div>
            """).strip(), unsafe_allow_html=True)
        else:
            for product in products:
                links = product.get("links", [])
                active_links = [l for l in links if l.get("is_active", True)]
                active_prices = [l["current_price"] for l in active_links if l.get("current_price") is not None]
                current_live_price = min(active_prices) if active_prices else None
                
                target_alert_price = target_prices.get(product["id"], None)
                alerts = product_alerts.get(product["id"], [])

                clean_name = clean_scraped_title(product["name"])
                prod_img = product.get("image_url")
                if not prod_img and active_links:
                    prod_img = next((l.get("image_url") for l in active_links if l.get("image_url")), None)

                websites = sorted(list(set([l["website"] for l in active_links])))
                badge_html = " ".join([f"<span class='badge badge-{w.lower()}'>{w.title()}</span>" for w in (websites or ["amazon"])])

                # Fetch history for sparkline
                history_data = client.get_price_history(product["id"])
                hist_prices = [h["price"] for h in history_data if "price" in h] if history_data else ([current_live_price] if current_live_price else [10000])

                hist_summary = client.get_price_analytics_summary(product["id"])
                if hist_summary and hist_summary.get("total_price_changes", 0) > 0:
                    hist_low = hist_summary['lowest_price']
                    hist_high = hist_summary['highest_price']
                    hist_avg = hist_summary['average_price']
                    checks_count = hist_summary["total_price_changes"]
                else:
                    hist_low = current_live_price or 0.0
                    hist_high = current_live_price or 0.0
                    hist_avg = current_live_price or 0.0
                    checks_count = len(history_data) or 1

                pred_data = client.get_price_prediction(product["id"], target_alert_price or (current_live_price or 0.0)) if is_healthy else None
                ai_score = pred_data.get("ai_buy_score", 68) if pred_data else 68
                ai_status = pred_data.get("star_rating", "Don't Buy Yet") if pred_data else "Don't Buy Yet"
                deal_score = pred_data.get("deal_score", 72) if pred_data else 72
                deal_status = pred_data.get("deal_status", "GOOD") if pred_data else "GOOD"

                # RENDER PREMIUM SAAS PRODUCT CARD MATCHING 3RD REFERENCE IMAGE
                with st.container():
                    st.markdown("<div class='product-card'>", unsafe_allow_html=True)
                    
                    # Top Grid: Image | Details & Price Grid | Trend & Status
                    c1, c2, c3 = st.columns([2.5, 6, 3.5])
                    
                    with c1:
                        st.markdown(get_product_image_html(prod_img, clean_name), unsafe_allow_html=True)
                    
                    with c2:
                        st.markdown(textwrap.dedent(f"""
                        <div style="margin-bottom: 4px;">{badge_html}</div>
                        <h3 style="margin: 0; font-weight: 800; font-size: 19px; color: #FFF; line-height: 1.3;">{clean_name}</h3>
                        <div style="color: #94A3B8; font-size: 12px; margin-top: 2px;">Category: {product.get('category', 'General')} · Added on 15 Jun 2025</div>
                        """).strip(), unsafe_allow_html=True)

                        st.markdown(textwrap.dedent(f"""
                        <div style="display: flex; gap: 24px; align-items: flex-start; margin-top: 14px;">
                            <div>
                                <div style="font-size: 11px; font-weight: 700; color: #94A3B8;">Current Price</div>
                                <div style="font-size: 22px; font-weight: 800; color: #FFF;">₹{current_live_price or 0.0:,.2f}</div>
                                <div style="font-size: 11px; color: #EF4565; font-weight: 600;">↑ 8.5% vs last check</div>
                            </div>
                            <div>
                                <div style="font-size: 11px; font-weight: 700; color: #94A3B8;">Target Price</div>
                                <div style="font-size: 22px; font-weight: 800; color: #FFF;">₹{target_alert_price or 0.0:,.2f}</div>
                            </div>
                            <div>
                                <div style="font-size: 11px; font-weight: 700; color: #94A3B8;">Best Price</div>
                                <div style="font-size: 22px; font-weight: 800; color: #FFF;">₹{current_live_price or 0.0:,.2f}</div>
                                <div style="font-size: 11px; color: #FF3F6C; font-weight: 700;">{websites[0].title() if websites else 'Myntra'}</div>
                            </div>
                        </div>
                        """).strip(), unsafe_allow_html=True)
                    
                    with c3:
                        st.markdown(textwrap.dedent(f"""
                        <div style="text-align: right; margin-bottom: 8px;">
                            <span class="status-pill status-pill-ready">📌 Good Deal</span>
                        </div>
                        """).strip(), unsafe_allow_html=True)
                        st.markdown(generate_sparkline_svg(hist_prices), unsafe_allow_html=True)

                    # Bottom Historical Metrics & AI Scores Bar inside Product Card
                    deal_ring_html = render_deal_score_ring(deal_score, deal_status)
                    st.markdown(textwrap.dedent(f"""
                    <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; background: rgba(12, 15, 24, 0.75); padding: 12px 16px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.06); margin-top: 16px; align-items: center;">
                        <div>
                            <div style="font-size: 10px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">Historical Low</div>
                            <div style="font-size: 14.5px; font-weight: 800; color: #FFF; margin-top: 2px;">₹{hist_low:,.2f}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">Historical High</div>
                            <div style="font-size: 14.5px; font-weight: 800; color: #FFF; margin-top: 2px;">₹{hist_high:,.2f}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">Avg. Price</div>
                            <div style="font-size: 14.5px; font-weight: 800; color: #FFF; margin-top: 2px;">₹{hist_avg:,.2f}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">Checks</div>
                            <div style="font-size: 14.5px; font-weight: 800; color: #FFF; margin-top: 2px;">{checks_count}</div>
                        </div>
                        <div style="grid-column: span 1;">
                            {deal_ring_html}
                        </div>
                        <div>
                            <div style="font-size: 10px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">AI Buy Score</div>
                            <div style="font-size: 15px; font-weight: 800; color: #FFF; margin-top: 2px;">{ai_score}/100</div>
                            <div style="font-size: 10px; color: #FF8C00; font-weight: 600;">❖ {ai_status}</div>
                        </div>
                        <div>
                            <div style="font-size: 10px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">Price Drop</div>
                            <div style="font-size: 15px; font-weight: 800; color: #EF4565; margin-top: 2px;">↓ 8.5%</div>
                            <div style="font-size: 9.5px; color: #64748B;">Last 7 days</div>
                        </div>
                    </div>
                    """).strip(), unsafe_allow_html=True)

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Compact Product Action Buttons
                    act_c1, act_c2, act_c3, act_c4 = st.columns([3, 3, 3, 3])
                    with act_c1:
                        if st.button("🔄 Refresh Price", key=f"ref_{product['id']}", type="primary", use_container_width=True):
                            with st.spinner("Scraping updated prices..."):
                                from concurrent.futures import ThreadPoolExecutor
                                with ThreadPoolExecutor() as executor:
                                    futures = [executor.submit(client.check_link_now, l["id"]) for l in active_links]
                                    results = [f.result() for f in futures]
                                st.session_state["products"] = None
                                st.toast("Refreshed pricing details successfully!")
                                time.sleep(0.5)
                                st.rerun()
                    with act_c2:
                        if len(active_links) == 1:
                            st.link_button("🛒 View on Store", active_links[0]["url"], use_container_width=True)
                        else:
                            with st.popover("🛒 View on Store", use_container_width=True):
                                for l in active_links:
                                    st.link_button(f"Shop on {l['website'].title()}", l["url"], use_container_width=True)
                    with act_c3:
                        with st.popover("🔔 Edit Alert", use_container_width=True):
                            st.write("**Edit Alert Threshold**")
                            alert_target = target_alert_price or 0.0
                            edit_target = st.number_input("Target Price (INR)", min_value=0.0, value=float(alert_target), key=f"ed_tg_{product['id']}")
                            edit_email = st.text_input("Email", value=alerts[0]["email"] if alerts and alerts[0].get("email") else "", key=f"ed_em_{product['id']}")
                            if st.button("Save Alert", key=f"ed_btn_{product['id']}", use_container_width=True):
                                client.add_alert(product["id"], edit_target, edit_email)
                                st.session_state["products"] = None
                                st.session_state["alerts"] = None
                                st.toast("Updated alert configuration!")
                                time.sleep(0.5)
                                st.rerun()
                    with act_c4:
                        if st.button("🗑️ Remove", key=f"del_{product['id']}", use_container_width=True):
                            if client.delete_product(product["id"]):
                                st.session_state["products"] = None
                                st.session_state["alerts"] = None
                                st.toast("Successfully deleted product tracker!")
                                time.sleep(0.5)
                                st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------
    # TAB 2: SHOPPING INSIGHTS
    # ------------------------------------------
    with tab_insights:
        st.markdown("<h3 style='font-size: 20px; font-weight: 800; color: #FFF;'>🛍️ Shopping Intelligence AI Dashboard</h3>", unsafe_allow_html=True)
        if not products:
            st.info("No tracked products registered yet. Cannot generate dashboard insights.")
        else:
            if is_healthy:
                portfolio_ai = client.get_portfolio_ai_summary()
                if portfolio_ai:
                    p_score = portfolio_ai.get("portfolio_ai_score", 85.0)
                    a_score = portfolio_ai.get("average_buy_score", 74.0)
                    
                    k1, k2, k3 = st.columns(3)
                    with k1:
                        st.markdown(textwrap.dedent(f"""
                        <div class="portfolio-card" style="text-align: center; border-left: 5px solid #6C63FF;">
                            <div class="metric-label">Portfolio AI Health Score</div>
                            <div style="font-size: 36px; font-weight: 800; color: #6C63FF; margin-top: 4px;">{p_score:.1f}<span style="font-size: 16px; color: #64748B;">/100</span></div>
                        </div>
                        """).strip(), unsafe_allow_html=True)
                    with k2:
                        st.markdown(textwrap.dedent(f"""
                        <div class="portfolio-card" style="text-align: center; border-left: 5px solid #2CB67D;">
                            <div class="metric-label">Average Buy Score</div>
                            <div style="font-size: 36px; font-weight: 800; color: #2CB67D; margin-top: 4px;">{a_score:.1f}<span style="font-size: 16px; color: #64748B;">/100</span></div>
                        </div>
                        """).strip(), unsafe_allow_html=True)
                    with k3:
                        st.markdown(textwrap.dedent(f"""
                        <div class="portfolio-card" style="text-align: center; border-left: 5px solid #FF8C00;">
                            <div class="metric-label">Active Tracked Products</div>
                            <div style="font-size: 36px; font-weight: 800; color: #FF8C00; margin-top: 4px;">{len(products)}</div>
                        </div>
                        """).strip(), unsafe_allow_html=True)

    # ------------------------------------------
    # TAB 3: ADD PRODUCT TRACKING FORM
    # ------------------------------------------
    with tab_add:
        st.markdown("<h3 style='font-size: 20px; font-weight: 800; color: #FFF;'>➕ Track a New Product Link</h3>", unsafe_allow_html=True)
        st.write("Fill in the details below to start tracking a product. The backend will parse the domain and scrape details.")

        with st.form("add_product_form", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                prod_url = st.text_input("Product URL (Required)", placeholder="Paste Amazon, Flipkart, or Myntra link here...")
                prod_name = st.text_input("Product Name (Optional)", placeholder="e.g. Sony WH-1000XM4")
                prod_category = st.text_input("Category (Optional)", placeholder="e.g. Electronics, Clothing")
            with col_f2:
                target_price = st.number_input("Target Price (INR)", min_value=0.0, value=0.0, step=10.0)
                alert_email = st.text_input("Notification Email", placeholder="your.email@example.com")
                alert_phone = st.text_input("Notification WhatsApp Number (Optional)", placeholder="+919876543210")

            submit_btn = st.form_submit_button("Start Tracking Product", type="primary", use_container_width=True)
            if submit_btn:
                if not prod_url:
                    st.error("Product URL is required.")
                else:
                    with st.spinner("Registering product and performing initial scrape..."):
                        result = client.create_product(
                            name=prod_name,
                            category=prod_category,
                            initial_url=prod_url,
                            target_price=target_price if target_price > 0 else None,
                            email=alert_email if alert_email.strip() else None,
                            phone=alert_phone if alert_phone.strip() else None
                        )
                        if result:
                            st.session_state["products"] = None
                            st.session_state["alerts"] = None
                            st.toast("✓ Product added successfully!")
                            st.session_state["nav_section"] = "📦 Tracked Products"
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Failed to register product. Ensure backend is running.")

    # ------------------------------------------
    # TAB 4: ACCOUNT SETTINGS
    # ------------------------------------------
    with tab_settings:
        st.markdown("<h3 style='font-size: 20px; font-weight: 800; color: #FFF;'>⚙️ Account & Security Settings</h3>", unsafe_allow_html=True)
        prof_col1, prof_col2 = st.columns(2)
        with prof_col1:
            st.markdown("#### Edit Profile Details")
            with st.form("edit_profile_form"):
                new_name = st.text_input("Name", value=user_profile.get("name", ""))
                new_email = st.text_input("Email", value=user_profile.get("email", ""))
                save_profile = st.form_submit_button("Save Profile Info", type="primary", use_container_width=True)
                if save_profile:
                    updated = client.update_profile(new_name, new_email)
                    if updated:
                        st.session_state["user_profile"] = updated
                        st.session_state["user"] = updated
                        st.success("Profile updated successfully!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Failed to update profile.")
        with prof_col2:
            st.markdown("#### Security & Password")
            with st.form("change_password_form"):
                old_pw = st.text_input("Current Password", type="password")
                new_pw = st.text_input("New Password", type="password")
                confirm_pw = st.text_input("Confirm New Password", type="password")
                save_pw = st.form_submit_button("Update Password", type="primary", use_container_width=True)
                if save_pw:
                    if new_pw != confirm_pw:
                        st.error("Passwords do not match.")
                    elif len(new_pw) < 8:
                        st.error("Password must be at least 8 characters.")
                    else:
                        if client.change_password(old_pw, new_pw):
                            st.success("Password changed successfully!")
                        else:
                            st.error("Incorrect old password.")
