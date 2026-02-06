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

st.header("🔎 Niche Trend Search")

niche = st.text_input("Enter a niche")
days = st.slider("Search videos from last X days", 1, 30, 5)

channel_type = st.radio("Channel Type", ["Both", "AI Generated", "Human Made"])

# ---------------- HELPERS ----------------

def generate_keywords(niche):
    patterns = [
        f"{niche} transformation", f"{niche} before and after", f"{niche} timelapse",
        f"{niche} full process", f"{niche} satisfying", f"{niche} restoration",
        f"{niche} repair", f"{niche} rebuild", f"{niche} makeover",
        f"extreme {niche}", f"{niche} project", f"how to {niche}",
        f"{niche} ASMR", f"{niche} cinematic", f"{niche} documentary"
    ]
    return list(set(patterns))

EMOTIONAL_WORDS = ["shocking","insane","unbelievable","satisfying","emotional","caught","exposed","transformation"]

def emotional_score(title):
    return sum(1 for w in EMOTIONAL_WORDS if re.search(w, title, re.IGNORECASE))

AI_KEYWORDS = ["ai generated","ai voice","text to speech","chatgpt","midjourney","stable diffusion","faceless"]
HUMAN_KEYWORDS = ["vlog","i built","i restored","watch me","my project","workshop","hands on"]

def detect_channel_type(title, description):
    text = f"{title} {description}".lower()
    if sum(w in text for w in AI_KEYWORDS) > sum(w in text for w in HUMAN_KEYWORDS):
        return "AI"
    elif sum(w in text for w in HUMAN_KEYWORDS) > sum(w in text for w in AI_KEYWORDS):
        return "Human"
    return "Unknown"

def analyze_titles(titles):
    words = []
    for t in titles:
        words.extend(re.findall(r'\b\w+\b', t.lower()))
    common = Counter(words).most_common(10)
    return ", ".join(w for w,_ in common)

# ---------------- SEARCH ----------------

if st.button("🔥 Find Viral Topics"):

    if not api_key or not niche:
        st.error("Enter API key and niche.")
        st.stop()

    keywords = generate_keywords(niche)
    start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"

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
        channel_ids = [i["snippet"]["channelId"] for i in items]

        video_stats = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
            "part": "statistics,snippet", "id": ",".join(video_ids), "key": api_key
        }).json().get("items", [])

        channel_stats = requests.get("https://www.googleapis.com/youtube/v3/channels", params={
            "part": "statistics,snippet", "id": ",".join(channel_ids), "key": api_key
        }).json().get("items", [])

        for v, vs, cs in zip(items, video_stats, channel_stats):
            views = int(vs["statistics"].get("viewCount", 0))
            subs = int(cs["statistics"].get("subscriberCount", 1))
            pub_date = datetime.strptime(vs["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            days_live = max((datetime.utcnow() - pub_date).days, 1)

            views_day = views / days_live
            ratio = views / max(subs, 1)
            emo = emotional_score(vs["snippet"]["title"])
            desc = vs["snippet"].get("description","")
            ctype = detect_channel_type(vs["snippet"]["title"], desc)

            viral_score = (views_day * 0.6) + (ratio * 0.3) + (emo * 10)

            if subs <= sub_limit:
                if channel_type == "AI Generated" and ctype != "AI":
                    continue
                if channel_type == "Human Made" and ctype != "Human":
                    continue

                results.append({
                    "Title": vs["snippet"]["title"],
                    "Channel": cs["snippet"]["title"],
                    "ChannelId": cs["id"],
                    "Keyword": keyword,
                    "Channel Type": ctype,
                    "Views": views,
                    "Views/Day": round(views_day,1),
                    "Subs": subs,
                    "V/S Ratio": round(ratio,2),
                    "Viral Score": round(viral_score,1),
                    "URL": f"https://youtube.com/watch?v={v['id']['videoId']}"
                })

    if not results:
        st.warning("No results found.")
        st.stop()

    df = pd.DataFrame(results).sort_values("Viral Score", ascending=False)

    st.subheader("🏆 Top 3 Viral Opportunities")
    top3 = df.head(3)

    for idx, row in top3.iterrows():
        st.markdown(f"### 🎯 {row['Title']}")
        st.markdown(f"🔗 [Watch Video]({row['URL']})")
        st.markdown(f"Channel: **{row['Channel']}** | Views/Day: **{row['Views/Day']}** | Viral Score: **{row['Viral Score']}**")

        if st.button(f"Analyze Channel: {row['Channel']}", key=row['ChannelId']):
            channel_videos = requests.get("https://www.googleapis.com/youtube/v3/search", params={
                "part": "snippet", "channelId": row["ChannelId"],
                "maxResults": 10, "order": "viewCount", "key": api_key
            }).json().get("items", [])

            titles = [v["snippet"]["title"] for v in channel_videos]
            st.write("**Common Title Words:**", analyze_titles(titles))
            st.write("**Total Videos Analyzed:**", len(titles))
            st.write("**Likely Content Pattern:** Repeating structure, emotional hooks, transformation or curiosity-driven titles.")

        st.write("---")

    st.subheader("📊 All Results")
    for _, r in df.iterrows():
        st.markdown(f"**{r['Title']}**  \n🔗 [Watch]({r['URL']}) | Views/Day: {r['Views/Day']} | Viral Score: {r['Viral Score']}")

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download CSV", csv, "viral_topics.csv", "text/csv")
