import streamlit as st
import requests
import json
import re
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

SETTINGS_FILE = "yt_settings.json"

# ---------------- SETTINGS ----------------
def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"api_key": "", "sub_limit": 5000}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

settings = load_settings()

# ---------------- UI ----------------
st.set_page_config(page_title="YouTube Viral Finder PRO", layout="wide")
st.title("🚀 YouTube Viral Niche Finder PRO")

st.sidebar.header("⚙ Settings")
api_key = st.sidebar.text_input("YouTube API Key", value=settings["api_key"], type="password")
sub_limit = st.sidebar.number_input("Max Subscriber Count", 0, 1_000_000, settings["sub_limit"])

if st.sidebar.button("💾 Save Settings"):
    settings["api_key"] = api_key
    settings["sub_limit"] = sub_limit
    save_settings(settings)
    st.sidebar.success("Saved!")

col1, col2 = st.columns(2)
with col1:
    niche = st.text_input("Enter a niche (e.g., 'Restoration')")
    days = st.slider("Search last X days", 1, 60, 7)
with col2:
    video_type = st.radio("Video Type", ["Both", "Shorts", "Long Videos"], horizontal=True)

# ---------------- HELPERS ----------------
def get_video_seconds(duration):
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match: return 0
    h = int(match.group(1)) if match.group(1) else 0
    m = int(match.group(2)) if match.group(2) else 0
    s = int(match.group(3)) if match.group(3) else 0
    return h * 3600 + m * 60 + s

def fetch_api(url, params):
    try:
        res = requests.get(url, params=params)
        return res.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return {}

def process_keyword(keyword, api_key, start_date):
    search_params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "order": "relevance", # Changed to relevance to find higher quality matches
        "publishedAfter": start_date,
        "maxResults": 15,
        "key": api_key
    }
    return fetch_api("https://www.googleapis.com/youtube/v3/search", search_params).get("items", [])

# ---------------- CORE LOGIC ----------------
if st.button("🔥 Find Viral Topics"):
    if not api_key or not niche:
        st.error("Missing API Key or Niche.")
        st.stop()

    start_date = (datetime.utcnow() - timedelta(days=days)).isoformat("T") + "Z"
    # Filter keywords to be more specific to high-performance formats
    keywords = [niche, f"{niche} transformation", f"{niche} satisfying", f"{niche} documentary"]
    
    all_video_ids = []
    video_data_map = {}

    with st.spinner("Searching YouTube (Concurrent Mode)..."):
        # Step 1: Concurrent Search
        with ThreadPoolExecutor(max_workers=5) as executor:
            search_results = list(executor.map(lambda k: process_keyword(k, api_key, start_date), keywords))
        
        flat_results = [item for sublist in search_results for item in sublist]
        unique_vids = {item["id"]["videoId"]: item for item in flat_results}.values()
        
        if not unique_vids:
            st.warning("No videos found. Try a broader niche.")
            st.stop()

        vid_ids = [v["id"]["videoId"] for v in unique_vids]
        
        # Step 2: Fetch Video Stats in Batches
        for i in range(0, len(vid_ids), 50):
            batch = vid_ids[i:i+50]
            stats = fetch_api("https://www.googleapis.com/youtube/v3/videos", {
                "part": "statistics,snippet,contentDetails",
                "id": ",".join(batch),
                "key": api_key
            }).get("items", [])
            for s in stats:
                video_data_map[s["id"]] = s

        # Step 3: Fetch Channel Stats
        channel_ids = list(set(v["snippet"]["channelId"] for v in video_data_map.values()))
        channel_map = {}
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i:i+50]
            c_stats = fetch_api("https://www.googleapis.com/youtube/v3/channels", {
                "part": "statistics,snippet",
                "id": ",".join(batch),
                "key": api_key
            }).get("items", [])
            for c in c_stats:
                channel_map[c["id"]] = c

    # Step 4: Filtering & Scoring
    results = []
    for vid, v_info in video_data_map.items():
        c_id = v_info["snippet"]["channelId"]
        if c_id not in channel_map: continue
        
        c_info = channel_map[c_id]
        subs = int(c_info["statistics"].get("subscriberCount", 0))
        
        # Subscriber Limit Filter
        if subs > sub_limit: continue
        
        duration = get_video_seconds(v_info["contentDetails"]["duration"])
        
        # Strict Video Type Logic
        is_short = duration <= 60
        if video_type == "Shorts" and not is_short: continue
        if video_type == "Long Videos" and is_short: continue

        views = int(v_info["statistics"].get("viewCount", 0))
        pub_date = datetime.strptime(v_info["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
        days_live = max((datetime.utcnow() - pub_date).days, 1)
        v_per_day = views / days_live
        
        # Viral Score Logic
        # A video is "Viral" if views/day is high relative to the channel size
        outlier_multiplier = v_per_day / (subs / 10 if subs > 100 else 10)
        viral_score = (v_per_day * 0.5) + (outlier_multiplier * 50)

        results.append({
            "Title": v_info["snippet"]["title"],
            "Channel": c_info["snippet"]["title"],
            "Views": views,
            "Subs": subs,
            "Views/Day": round(v_per_day, 1),
            "Score": round(viral_score, 1),
            "Link": f"https://youtube.com/watch?v={vid}"
        })

    if results:
        df = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.dataframe(df, use_container_width=True)
        
        for _, row in df.head(10).iterrows():
            with st.expander(f"⭐ Score: {row['Score']} | {row['Title']}"):
                st.write(f"**Channel:** {row['Channel']} ({row['Subs']} subs)")
                st.write(f"**Performance:** {row['Views']} total views ({row['Views/Day']} per day)")
                st.link_button("Watch Video", row['Link'])
    else:
        st.info("No 'outlier' videos found matching these specific filters.")
