import streamlit as st
import requests
import json
import re
import pandas as pd
from datetime import datetime, timedelta

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

st.title("🚀 YouTube Viral Niche Finder")

st.sidebar.header("⚙ Settings")

api_key = st.sidebar.text_input("YouTube API Key", value=settings["api_key"], type="password")
sub_limit = st.sidebar.number_input("Max Subscriber Count", 0, 1_000_000, settings["sub_limit"])

if st.sidebar.button("💾 Save Settings"):
    settings["api_key"] = api_key
    settings["sub_limit"] = sub_limit
    save_settings(settings)
    st.sidebar.success("Saved!")

st.header("🔎 Niche Trend Search")

niche = st.text_input("Enter a niche (example: car restoration, tech repair, reddit stories)")
days = st.slider("Search videos from last X days", 1, 30, 5)

channel_type = st.radio(
    "Channel Type",
    ["Both", "AI Generated", "Human Made"]
)

# ---------------- KEYWORD GENERATOR ----------------

def generate_keywords(niche):
    patterns = [
        f"{niche} transformation",
        f"{niche} before and after",
        f"{niche} timelapse",
        f"{niche} full process",
        f"{niche} satisfying",
        f"{niche} restoration",
        f"{niche} repair",
        f"{niche} rebuild",
        f"{niche} makeover",
        f"extreme {niche}",
        f"{niche} project",
        f"how to {niche}",
        f"{niche} ASMR",
        f"{niche} cinematic",
        f"{niche} documentary",
    ]
    return list(set(patterns))

# ---------------- TITLE ANALYZER ----------------

EMOTIONAL_WORDS = ["shocking", "insane", "unbelievable", "satisfying", "emotional", "caught", "exposed", "transformation"]

def emotional_score(title):
    return sum(1 for word in EMOTIONAL_WORDS if re.search(word, title, re.IGNORECASE))

# ---------------- CHANNEL TYPE DETECTION ----------------

AI_KEYWORDS = ["ai generated", "ai voice", "text to speech", "chatgpt", "midjourney", "stable diffusion", "faceless"]
HUMAN_KEYWORDS = ["vlog", "i built", "i restored", "watch me", "my project", "workshop", "hands on"]

def detect_channel_type(title, description):
    text = f"{title} {description}".lower()
    ai_score = sum(word in text for word in AI_KEYWORDS)
    human_score = sum(word in text for word in HUMAN_KEYWORDS)

    if ai_score > human_score:
        return "AI"
    elif human_score > ai_score:
        return "Human"
    return "Unknown"

# ---------------- FETCH DATA ----------------

if st.button("🔥 Find Viral Topics"):

    if not api_key or not niche:
        st.error("Enter API key and niche.")
        st.stop()

    keywords = generate_keywords(niche)
    start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"

    YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
    YT_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
    YT_CHANNELS = "https://www.googleapis.com/youtube/v3/channels"

    results = []

    for keyword in keywords:
        params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": start_date,
            "maxResults": 5,
            "key": api_key
        }

        search_res = requests.get(YT_SEARCH, params=params).json()
        items = search_res.get("items", [])
        if not items:
            continue

        video_ids = [i["id"]["videoId"] for i in items]
        channel_ids = [i["snippet"]["channelId"] for i in items]

        video_stats = requests.get(YT_VIDEOS, params={
            "part": "statistics,snippet",
            "id": ",".join(video_ids),
            "key": api_key
        }).json().get("items", [])

        channel_stats = requests.get(YT_CHANNELS, params={
            "part": "statistics",
            "id": ",".join(channel_ids),
            "key": api_key
        }).json().get("items", [])

        for v, vs, cs in zip(items, video_stats, channel_stats):
            views = int(vs["statistics"].get("viewCount", 0))
            subs = int(cs["statistics"].get("subscriberCount", 1))
            pub_date = datetime.strptime(vs["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            days_live = max((datetime.utcnow() - pub_date).days, 1)

            views_day = views / days_live
            ratio = views / max(subs, 1)
            emo_score = emotional_score(vs["snippet"]["title"])
            description = vs["snippet"].get("description", "")
            ctype = detect_channel_type(vs["snippet"]["title"], description)

            viral_score = (views_day * 0.6) + (ratio * 0.3) + (emo_score * 10)

            if subs <= sub_limit:
                if channel_type == "AI Generated" and ctype != "AI":
                    continue
                if channel_type == "Human Made" and ctype != "Human":
                    continue

                results.append({
                    "Title": vs["snippet"]["title"],
                    "Keyword": keyword,
                    "Channel Type": ctype,
                    "Views": views,
                    "Views/Day": round(views_day, 1),
                    "Subs": subs,
                    "V/S Ratio": round(ratio, 2),
                    "Emotional Score": emo_score,
                    "Viral Score": round(viral_score, 1),
                    "URL": f"https://youtube.com/watch?v={v['id']['videoId']}"
                })

    if not results:
        st.warning("No results found. Try broader niche.")
        st.stop()

    df = pd.DataFrame(results).sort_values("Viral Score", ascending=False)

    st.success("Top Viral Opportunities Found!")
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download CSV", csv, "viral_topics.csv", "text/csv")
