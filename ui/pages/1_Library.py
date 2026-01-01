"""Library page - View and sync videos."""

import streamlit as st
import httpx
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Library - YT-Assist", page_icon="📚", layout="wide")

API_BASE = "http://127.0.0.1:8000/api"


def format_duration(seconds: int | None) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    if not seconds:
        return "-"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_date(date_str: str | None) -> str:
    """Format ISO date to readable format."""
    if not date_str:
        return "-"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10] if date_str else "-"


def get_status_icon(status: str, has_transcript: bool) -> str:
    """Get status icon for display."""
    if status == "synced":
        return "✅" if has_transcript else "⚠️"
    elif status == "error":
        return "❌"
    return "⏳"


st.title("📚 Video Library")

# Sync status section
st.markdown("### Sync Status")

col1, col2, col3, col4 = st.columns(4)

try:
    status_response = httpx.get(f"{API_BASE}/sync/status", timeout=5.0)
    if status_response.status_code == 200:
        status = status_response.json()
        col1.metric("Total Videos", status["total_videos"])
        col2.metric("Synced", status["synced"])
        col3.metric("Pending", status["pending"])
        col4.metric("Errors", status["errors"])
    else:
        st.error("Failed to fetch sync status")
except httpx.ConnectError:
    st.error("Cannot connect to API. Make sure the server is running.")
    st.code("uvicorn app.main:app --reload", language="bash")
    st.stop()
except Exception as e:
    st.error(f"Error: {e}")
    st.stop()

st.markdown("---")

# Sync actions
st.markdown("### Actions")

col_sync, col_export = st.columns(2)

with col_sync:
    if st.button("🔄 Sync All Videos", type="primary", use_container_width=True):
        with st.spinner("Syncing videos from YouTube... This may take a while."):
            try:
                response = httpx.post(
                    f"{API_BASE}/sync/all",
                    json={},
                    timeout=300.0,  # 5 min timeout for large channels
                )
                if response.status_code == 200:
                    result = response.json()
                    st.success(result["message"])

                    # Show summary
                    summary = result["summary"]
                    st.info(
                        f"Synced: {summary['synced']} | "
                        f"Pending: {summary['pending']} | "
                        f"Errors: {summary['errors']}"
                    )
                    st.rerun()
                else:
                    st.error(f"Sync failed: {response.text}")
            except Exception as e:
                st.error(f"Sync error: {e}")

with col_export:
    exp_col1, exp_col2 = st.columns(2)

    with exp_col1:
        if st.button("📥 Export JSONL", use_container_width=True):
            try:
                response = httpx.get(f"{API_BASE}/export/jsonl", timeout=60.0)
                if response.status_code == 200:
                    st.download_button(
                        label="Download JSONL",
                        data=response.content,
                        file_name="transcripts.jsonl",
                        mime="application/x-ndjson",
                    )
            except Exception as e:
                st.error(f"Export error: {e}")

    with exp_col2:
        if st.button("📦 Export ZIP", use_container_width=True):
            try:
                response = httpx.get(f"{API_BASE}/export/zip", timeout=60.0)
                if response.status_code == 200:
                    st.download_button(
                        label="Download ZIP",
                        data=response.content,
                        file_name="transcripts.zip",
                        mime="application/zip",
                    )
            except Exception as e:
                st.error(f"Export error: {e}")

st.markdown("---")

# Filters
st.markdown("### Videos")

filter_col1, filter_col2 = st.columns([1, 3])

with filter_col1:
    status_filter = st.selectbox(
        "Filter by status",
        options=["All", "synced", "pending", "error"],
        index=0,
    )

with filter_col2:
    search_query = st.text_input("Search by title", placeholder="Enter search term...")

# Fetch videos
params = {"page": 1, "page_size": 100}
if status_filter != "All":
    params["status"] = status_filter
if search_query:
    params["search"] = search_query

try:
    response = httpx.get(f"{API_BASE}/videos", params=params, timeout=10.0)
    if response.status_code == 200:
        data = response.json()
        videos = data["items"]
        total = data["total"]

        if videos:
            st.caption(f"Showing {len(videos)} of {total} videos")

            # Build dataframe
            df_data = []
            for v in videos:
                df_data.append({
                    "Status": get_status_icon(v["sync_status"], v["has_transcript"]),
                    "Title": v["title"][:60] + ("..." if len(v["title"]) > 60 else ""),
                    "Published": format_date(v["published_at"]),
                    "Duration": format_duration(v["duration_seconds"]),
                    "Views": f"{v['view_count']:,}" if v.get("view_count") else "-",
                    "Transcript": "Yes" if v["has_transcript"] else "No",
                    "ID": v["id"],
                })

            df = pd.DataFrame(df_data)

            # Display as table
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Title": st.column_config.TextColumn("Title", width="large"),
                    "Published": st.column_config.TextColumn("Published", width="small"),
                    "Duration": st.column_config.TextColumn("Duration", width="small"),
                    "Views": st.column_config.TextColumn("Views", width="small"),
                    "Transcript": st.column_config.TextColumn("Transcript", width="small"),
                    "ID": st.column_config.TextColumn("Video ID", width="medium"),
                },
            )

            # Video details expander
            st.markdown("### Video Details")
            selected_id = st.selectbox(
                "Select a video to view details",
                options=[v["id"] for v in videos],
                format_func=lambda x: next(
                    (v["title"][:50] for v in videos if v["id"] == x), x
                ),
            )

            if selected_id:
                try:
                    detail_response = httpx.get(
                        f"{API_BASE}/videos/{selected_id}", timeout=10.0
                    )
                    if detail_response.status_code == 200:
                        video = detail_response.json()

                        with st.expander("📹 Video Info", expanded=True):
                            st.markdown(f"**Title:** {video['title']}")
                            st.markdown(f"**Video ID:** `{video['id']}`")
                            st.markdown(
                                f"**YouTube Link:** "
                                f"[Watch on YouTube](https://youtube.com/watch?v={video['id']})"
                            )
                            st.markdown(f"**Published:** {format_date(video['published_at'])}")
                            st.markdown(f"**Duration:** {format_duration(video['duration_seconds'])}")

                            if video.get("tags"):
                                st.markdown(f"**Tags:** {', '.join(video['tags'][:10])}")

                            if video.get("description"):
                                with st.expander("Description"):
                                    st.text(video["description"][:1000])

                        if video.get("transcripts"):
                            with st.expander("📝 Transcript", expanded=False):
                                for t in video["transcripts"]:
                                    st.markdown(
                                        f"**Language:** {t['language_code']} | "
                                        f"**Auto-generated:** {t['is_auto_generated']}"
                                    )
                                    st.text_area(
                                        "Content",
                                        value=t["clean_content"][:5000],
                                        height=300,
                                        disabled=True,
                                    )
                        else:
                            st.warning("No transcript available for this video")

                            # Option to sync single video
                            if st.button(f"Sync this video", key=f"sync_{selected_id}"):
                                with st.spinner("Syncing..."):
                                    sync_response = httpx.post(
                                        f"{API_BASE}/sync/video/{selected_id}",
                                        timeout=60.0,
                                    )
                                    if sync_response.status_code == 200:
                                        result = sync_response.json()
                                        if result["success"]:
                                            st.success("Video synced!")
                                            st.rerun()
                                        else:
                                            st.error(f"Sync failed: {result.get('error')}")
                except Exception as e:
                    st.error(f"Error fetching video details: {e}")
        else:
            st.info("No videos found. Click 'Sync All Videos' to fetch from YouTube.")
    else:
        st.error(f"Failed to fetch videos: {response.text}")
except Exception as e:
    st.error(f"Error: {e}")
