"""Streamlit main application entry point."""

import streamlit as st

st.set_page_config(
    page_title="YT-Assist",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("YT-Assist")
st.markdown("### Ardalan YouTube AI Assistant")

st.markdown("""
Welcome to YT-Assist! This tool helps you manage and leverage your YouTube channel content.

**Current Features (Milestone 1):**
- Sync videos and transcripts from your YouTube channel
- View all videos with sync status
- Export transcripts as JSONL or ZIP

**Getting Started:**
1. Make sure the API server is running: `uvicorn app.main:app --reload`
2. Go to **Library** to sync and view your videos
3. Use **Export** to download your transcripts

---

**Navigation:** Use the sidebar to navigate between pages.
""")

# Sidebar info
with st.sidebar:
    st.markdown("---")
    st.markdown("**API Status**")

    import httpx
    try:
        response = httpx.get("http://127.0.0.1:8000/health", timeout=2.0)
        if response.status_code == 200:
            st.success("API Connected")
        else:
            st.error("API Error")
    except Exception:
        st.warning("API Not Running")
        st.caption("Start with: `uvicorn app.main:app --reload`")
