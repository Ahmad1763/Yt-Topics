    for keyword in keywords:
        search_res = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "order": "date",  # 🔥 FIXED (was viewCount)
            "publishedAfter": start_date,
            "maxResults": 10,
            "key": api_key
        }).json()

        items = search_res.get("items", [])

        # 🔁 Fallback: if no recent results, try without date filter
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
