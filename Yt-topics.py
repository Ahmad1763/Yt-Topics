if st.button("🔥 Find Viral Topics"):

    if not api_key or not niche:
        st.error("Enter API key and niche.")
        st.stop()

    start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"
    keywords = generate_keywords(niche)
    results = []

    for keyword in keywords:
        # ---- PRIMARY SEARCH (recent videos) ----
        search_res = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "order": "date",
            "publishedAfter": start_date,
            "maxResults": 10,
            "key": api_key
        }).json()

        items = search_res.get("items", [])

        # ---- FALLBACK SEARCH (popular videos if recent empty) ----
        if not items:
            search_res = requests.get("https://www.googleapis.com/youtube/v3/search", params={
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "order": "viewCount",
                "maxResults": 5,
                "key": api_key
            }).json()
            items = search_res.get("items", [])

        if not items:
            continue

        video_ids = [i["id"]["videoId"] for i in items]
        channel_ids = list(set(i["snippet"]["channelId"] for i in items))

        # Fetch video details
        video_stats = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
            "part": "statistics,snippet",
            "id": ",".join(video_ids),
            "key": api_key
        }).json().get("items", [])

        # Fetch channel details
        channel_stats = requests.get("https://www.googleapis.com/youtube/v3/channels", params={
            "part": "statistics,snippet",
            "id": ",".join(channel_ids),
            "key": api_key
        }).json().get("items", [])

        video_map = {v["id"]: v for v in video_stats}
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
                continue

            pub_date = datetime.strptime(vs["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            days_live = max((datetime.utcnow() - pub_date).days, 1)
            views_day = views / days_live
            viral_score = (views_day * 0.7) + (emotional_score(vs["snippet"]["title"]) * 10)

            results.append({
                "Title": vs["snippet"]["title"],
                "Channel": cs["snippet"]["title"],
                "ChannelId": cid,
                "Views/Day": round(views_day, 1),
                "Viral Score": round(viral_score, 1),
                "URL": f"https://youtube.com/watch?v={vid}"
            })

    if not results:
        st.warning("No results found. Try broader niche.")
        st.stop()

    df = pd.DataFrame(results).sort_values("Viral Score", ascending=False)
