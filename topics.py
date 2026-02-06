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

# ---------------- UI SETUP ----------------
st.set_page_config(page_title="YouTube Growth Dashboard", layout="wide")
st.title("📈 YouTube Viral Growth & Competitor Dashboard")

st.sidebar.header("⚙️ Global Settings")
api_key = st.sidebar.text_input("YouTube API Key", value=settings["api_key"], type="password")
sub_limit = st.sidebar.number_input("Max Subscriber Count (Small Channels)", 0, 1_000_000, settings["sub_limit"])

if st.sidebar.button("💾 Save Settings"):
    settings["api_key"] = api_key
    settings["sub_limit"] = sub_limit
    save_settings(settings)
    st.sidebar.success("Settings Saved!")

tab1, tab2 = st.tabs(["🔥 Viral Outlier Finder", "🕵️ Competitor Deep Dive"])

# ---------------- HELPERS ----------------
def get_video_seconds(duration):
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match: return 0
    h, m, s = [int(match.group(i)) if match.group(i) else 0 for i in range(1, 4)]
    return h * 3600 + m * 60 + s

def fetch_api(url, params):
    try:
        res = requests.get(url, params=params)
        return res.json()
    except: return {}

# ---------------- TAB 1: OUTLIER FINDER ----------------
with tab1:
    col_a, col_b = st.columns(2)
    with col_a:
        niche = st.text_input("Niche Topic", placeholder="e.g. Phone Restoration")
        days = st.slider("Published within last X days", 1, 90, 14)
    with col_b:
        video_type = st.radio("Format", ["Both", "Shorts", "Long Videos"], horizontal=True)
        min_outlier = st.slider("Min Outlier Score (e.g. 3x better than usual)", 1.0, 20.0, 2.0)

    if st.button("🚀 Find High-Performance Ideas"):
        if not api_key or not niche:
            st.error("Please provide an API key and Niche.")
            st.stop()

        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat("T") + "Z"
        keywords = [niche, f"{niche} transformation", f"{niche} how to", f"{niche} extreme"]
        
        results = []
        with st.spinner("Scanning for Outliers..."):
            # Concurrent keyword search
            with ThreadPoolExecutor(max_workers=4) as exec:
                search_jobs = [exec.submit(fetch_api, "https://www.googleapis.com/youtube/v3/search", 
                    {"part": "snippet", "q": k, "type": "video", "publishedAfter": start_date, "maxResults": 20, "key": api_key}) for k in keywords]
                
            all_items = []
            for job in search_jobs:
                all_items.extend(job.result().get("items", []))
            
            unique_vids = {i["id"]["videoId"]: i for i in all_items}.keys()
            
            # Batch fetch stats
            vid_stats = fetch_api("https://www.googleapis.com/youtube/v3/videos", {"part": "statistics,contentDetails,snippet", "id": ",".join(list(unique_vids)[:50]), "key": api_key}).get("items", [])
            chan_ids = list(set(v["snippet"]["channelId"] for v in vid_stats))
            chan_stats = {c["id"]: c for c in fetch_api("https://www.googleapis.com/youtube/v3/channels", {"part": "statistics,snippet", "id": ",".join(chan_ids[:50]), "key": api_key}).get("items", [])}

            for v in vid_stats:
                cid = v["snippet"]["channelId"]
                if cid not in chan_stats: continue
                
                subs = int(chan_stats[cid]["statistics"].get("subscriberCount", 0))
                if subs > sub_limit or subs < 10: continue # Filter for small creators
                
                duration = get_video_seconds(v["contentDetails"]["duration"])
                is_short = duration <= 60
                if (video_type == "Shorts" and not is_short) or (video_type == "Long Videos" and is_short): continue

                views = int(v["statistics"].get("viewCount", 0))
                # Outlier Calculation: How much better is this than their sub count?
                outlier_score = round(views / (subs if subs > 0 else 1), 2)
                
                if outlier_score >= min_outlier:
                    results.append({
                        "Title": v["snippet"]["title"],
                        "Outlier Ratio": f"{outlier_score}x",
                        "Views": views,
                        "Subs": subs,
                        "Link": f"https://youtube.com/watch?v={v['id']}",
                        "ChannelId": cid
                    })

        if results:
            df = pd.DataFrame(results).sort_values("Outlier Ratio", ascending=False)
            st.success(f"Found {len(results)} outlier videos!")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No outliers found with current filters.")

# ---------------- TAB 2: COMPETITOR DEEP DIVE ----------------
with tab2:
    target_channel = st.text_input("Enter Channel ID to Analyze", help="Find it in the Channel URL or Tab 1 results")
    
    if st.button("🔍 Analyze Content Strategy"):
        with st.spinner("Deconstructing Channel Strategy..."):
            # 1. Get top 15 videos
            top_vids = fetch_api("https://www.googleapis.com/youtube/v3/search", {
                "part": "snippet", "channelId": target_channel, "order": "viewCount", "maxResults": 15, "type": "video", "key": api_key
            }).get("items", [])
            
            titles = [v["snippet"]["title"] for v in top_vids]
            
            # 2. Pattern Analysis
            words = []
            for t in titles:
                words.extend(re.findall(r'\b\w{4,}\b', t.lower())) # Only words > 3 letters
            common_words = Counter(words).most_common(10)
            
            # 3. UI Display
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🗝️ Winning Keywords")
                for word, count in common_words:
                    st.write(f"- **{word}** (Used in {count} top videos)")
            
            with c2:
                st.subheader("📖 Story Archetype")
                if any(w in " ".join(titles).lower() for w in ["how", "tutorial", "guide"]):
                    st.info("Strategy: **Educational Authority**. This channel grows by solving specific problems.")
                elif any(w in " ".join(titles).lower() for w in ["transformation", "before", "restored"]):
                    st.info("Strategy: **Visual Satisfaction**. This channel grows by showing extreme progress.")
                else:
                    st.info("Strategy: **Entertainment/Vlog**. Focuses on personality or high-stakes hooks.")
            
            st.divider()
            st.subheader("📋 Top Video Analysis")
            for t in titles[:5]:
                st.write(f"✅ **Viral Hook:** {t}")
                st.caption("Suggested replicable angle: 'I tried [Keyword] for 30 days...' or '[Keyword]: The Hidden Truth'")
