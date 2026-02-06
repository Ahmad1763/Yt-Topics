import streamlit as st
import requests
import json
import re
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter

SETTINGS_FILE = "yt_settings.json"

# ---------------- SETTINGS ----------------

def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"api_key": "", "sub_limit": 3000}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

settings = load_settings()

# ---------------- UI ----------------

st.title("🚀 YouTube Viral Niche Finder PRO")

st.sidebar.header("⚙ Settings")
api_key = st.sidebar.text_input("YouTube API Key", value=settings["api_key"], type="password")
sub_limit = st.sidebar.number_input("Max Subscriber Count", 0, 1_000_000, settings["sub_limit"])

if st.sidebar.button("💾 Save Settings"):
    settings["api_key"] = api_key
    settings["sub_limit"] = sub_limit
    save_settings(settings)
    st.sidebar.success("Saved!")

niche = st.text_input("Enter a niche")
days = st.slider("Search last X days", 1, 30, 5)
channel_type = st.radio("Channel Type", ["Both", "AI Generated", "Human Made"])

# ---------------- HELPERS ----------------

def generate_keywords(niche):
    return list(set([
        f"{niche} transformation", f"{niche} before and after",
        f"{niche} timelapse", f"{niche} full process",
        f"{niche} satisfying", f"{niche} restoration",
        f"{niche} repair", f"{niche} rebuild"
    ]))

def emotional_score(title):
    words = ["shocking","insane","unbelievable","satisfying","exposed","transformation"]
    return sum(1 for w in words if w in title.lower())

def analyze_titles(titles):
    words = []
    for t in titles:
        words.extend(re.findall(r'\b\w+\b', t.lower()))
    return ", ".join(w for w,_ in Counter(words).most_common(8))

# ---------------- SEARCH ----------------

if st.button("🔥 Find Viral Topics"):

    if not api_key or not niche:
        st.error("Enter API key and niche.")
        st.stop()

    start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"
    keywords = generate_keywords(niche)
    results = []

    for keyword in keywords:
        search_res = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet", "q": keyword, "type": "video",
            "order": "viewCount", "publishedAfter": start_date,
            "maxResults": 5, "key": api_key
        }).json()

        items = search_res.get("items", [])
        if not items:
            continue

        video_ids = [i["id"]["videoId"] for i in items]
        channel_ids = list(set(i["snippet"]["channelId"] for i in items))

        # Fetch video stats
        video_stats = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
            "part": "statistics,snippet",
            "id": ",".join(video_ids),
            "key": api_key
        }).json().get("items", [])

        # Map by videoId
        video_map = {v["id"]: v for v in video_stats}

        # Fetch channel stats
        channel_stats = requests.get("https://www.googleapis.com/youtube/v3/channels", params={
            "part": "statistics,snippet",
            "id": ",".join(channel_ids),
            "key": api_key
        }).json().get("items", [])

        # Map by channelId
        channel_map = {c["id"]: c for c in channel_stats}

        for item in items:
            vid = item["id"]["videoId"]
            cid = item["snippet"]["channelId"]

            if vid not in video_map or cid not in channel_map:
                continue

            vs = video_map[vid]
            cs = channel_map[cid]

            views = int(vs["statistics"].get("viewCount", 0))
            subs = int(cs["statistics"].get("subscriberCount", 0))

            if subs > sub_limit:
                continue  # FIXED subscriber filter

            pub_date = datetime.strptime(vs["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            days_live = max((datetime.utcnow() - pub_date).days, 1)
            views_day = views / days_live
            viral_score = (views_day * 0.7) + (emotional_score(vs["snippet"]["title"]) * 10)

            results.append({
                "Title": vs["snippet"]["title"],
                "Channel": cs["snippet"]["title"],
                "ChannelId": cid,
                "Views/Day": round(views_day,1),
                "Viral Score": round(viral_score,1),
                "URL": f"https://youtube.com/watch?v={vid}"
            })

    if not results:
        st.warning("No results found.")
        st.stop()

    df = pd.DataFrame(results).sort_values("Viral Score", ascending=False)

    st.subheader("🏆 Top 3 Opportunities")
    for i, row in df.head(3).iterrows():
        st.markdown(f"### 🎯 {row['Title']}")
        st.markdown(f"🔗 [Watch Video]({row['URL']})")
        st.markdown(f"Channel: **{row['Channel']}** | Views/Day: **{row['Views/Day']}**")

        if st.button(f"Analyze Channel {row['Channel']}", key=f"analyze_{row['ChannelId']}"):
            with st.spinner("Analyzing channel..."):
                ch_videos = requests.get("https://www.googleapis.com/youtube/v3/search", params={
                    "part": "snippet",
                    "channelId": row["ChannelId"],
                    "maxResults": 10,
                    "order": "date",
                    "type": "video",
                    "key": api_key
                }).json().get("items", [])

                titles = [v["snippet"]["title"] for v in ch_videos]
                st.write("**Recent Title Patterns:**", analyze_titles(titles))
                st.write("**Upload Style Insight:** Likely follows repeatable formatting and strong curiosity hooks.")

        st.write("---")

    st.subheader("📊 All Results")
    for _, r in df.iterrows():
        st.markdown(f"**{r['Title']}**  \n🔗 [Watch]({r['URL']}) | Viral Score: {r['Viral Score']}")
