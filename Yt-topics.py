import streamlit as st
import requests
import json
from datetime import datetime, timedelta

SETTINGS_FILE = "yt_settings.json"

# ------------------ LOAD / SAVE SETTINGS ------------------

def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "api_key": "",
            "keywords": ["Reddit Stories", "AITA Update"],
            "sub_limit": 3000
        }

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

settings = load_settings()

# ------------------ UI ------------------

st.title("🔥 YouTube Viral Topic Finder Pro")

st.sidebar.header("⚙️ Settings")

api_key = st.sidebar.text_input("YouTube API Key", value=settings["api_key"], type="password")

keywords_input = st.sidebar.text_area(
    "Keywords (one per line)",
    value="\n".join(settings["keywords"]),
    height=200
)

sub_limit = st.sidebar.number_input(
    "Max Subscriber Count",
    min_value=0,
    max_value=1_000_000,
    value=settings["sub_limit"]
)

if st.sidebar.button("💾 Save Settings"):
    settings["api_key"] = api_key
    settings["keywords"] = [k.strip() for k in keywords_input.split("\n") if k.strip()]
    settings["sub_limit"] = sub_limit
    save_settings(settings)
    st.sidebar.success("Settings saved!")

st.header("🔍 Search Parameters")

days = st.number_input("Search videos from the last X days:", 1, 30, 5)

sort_option = st.selectbox(
    "Sort Results By:",
    ["Views per Day", "Total Views", "Views/Sub Ratio"]
)

# ------------------ FETCH DATA ------------------

if st.button("🚀 Find Viral Opportunities"):

    if not api_key:
        st.error("Please enter your API key in the sidebar.")
        st.stop()

    YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
    YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

    start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"
    keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]
    results = []

    progress = st.progress(0)
    total_keywords = len(keywords)

    for i, keyword in enumerate(keywords):
        st.write(f"Searching: **{keyword}**")

        search_params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": start_date,
            "maxResults": 5,
            "key": api_key,
        }

        res = requests.get(YOUTUBE_SEARCH_URL, params=search_params).json()
        videos = res.get("items", [])
        if not videos:
            continue

        video_ids = [v["id"]["videoId"] for v in videos]
        channel_ids = [v["snippet"]["channelId"] for v in videos]

        stats = requests.get(YOUTUBE_VIDEO_URL, params={
            "part": "statistics,snippet",
            "id": ",".join(video_ids),
            "key": api_key
        }).json().get("items", [])

        channels = requests.get(YOUTUBE_CHANNEL_URL, params={
            "part": "statistics",
            "id": ",".join(channel_ids),
            "key": api_key
        }).json().get("items", [])

        for vid, stat, ch in zip(videos, stats, channels):
            views = int(stat["statistics"].get("viewCount", 0))
            subs = int(ch["statistics"].get("subscriberCount", 1))
            pub_date = datetime.strptime(stat["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            days_live = max((datetime.utcnow() - pub_date).days, 1)

            views_per_day = views / days_live
            view_sub_ratio = views / max(subs, 1)

            if subs <= sub_limit:
                results.append({
                    "Title": stat["snippet"]["title"],
                    "URL": f"https://youtube.com/watch?v={vid['id']['videoId']}",
                    "Views": views,
                    "Subs": subs,
                    "Views/Day": round(views_per_day, 1),
                    "Views/Sub Ratio": round(view_sub_ratio, 2)
                })

        progress.progress((i + 1) / total_keywords)

    if not results:
        st.warning("No viral opportunities found. Try adjusting keywords or subscriber limit.")
        st.stop()

    # Sorting
    if sort_option == "Views per Day":
        results.sort(key=lambda x: x["Views/Day"], reverse=True)
    elif sort_option == "Views/Sub Ratio":
        results.sort(key=lambda x: x["Views/Sub Ratio"], reverse=True)
    else:
        results.sort(key=lambda x: x["Views"], reverse=True)

    st.success(f"Found {len(results)} potential viral videos!")

    for r in results:
        st.markdown(f"""
**🎬 {r['Title']}**  
🔗 [Watch Video]({r['URL']})  
👀 Views: {r['Views']}  
📈 Views/Day: {r['Views/Day']}  
🔥 Views/Sub Ratio: {r['Views/Sub Ratio']}  
👤 Subs: {r['Subs']}  
---
""")
