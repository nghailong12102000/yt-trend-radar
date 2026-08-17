"""Bước 1: kéo dữ liệu trending đa quốc gia + subscriber count + autocomplete.

Quota: videos.list = 1 unit/call, channels.list = 1 unit/call.
16 region x 11 category ~ 176 unit + ~60 unit channels = ~240/10.000 mỗi ngày.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests

import config

API_KEY = os.environ.get("YOUTUBE_API_KEY")
BASE = "https://www.googleapis.com/youtube/v3"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def iso_duration_to_sec(iso: str) -> int:
    """PT1H2M10S -> 3730"""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def get(endpoint: str, params: dict) -> dict:
    params["key"] = API_KEY
    for attempt in range(3):
        r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (403, 429):
            # quota hoặc rate limit -> dừng hẳn, retry vô ích
            print(f"  ! {r.status_code}: {r.text[:200]}", file=sys.stderr)
            if "quotaExceeded" in r.text:
                raise SystemExit("Hết quota YouTube API cho hôm nay.")
            return {}
        time.sleep(2 ** attempt)
    return {}


# --------------------------------------------------------------------------- #
# Trending
# --------------------------------------------------------------------------- #
def fetch_trending(region: str, category_id: str) -> list[dict]:
    data = get("videos", {
        "part": "snippet,statistics,contentDetails",
        "chart": "mostPopular",
        "regionCode": region,
        "videoCategoryId": category_id,
        "maxResults": 50,
    })
    rows = []
    for item in data.get("items", []):
        sn, st = item.get("snippet", {}), item.get("statistics", {})
        views = int(st.get("viewCount", 0) or 0)
        if views < config.MIN_VIEWS:
            continue
        rows.append({
            "video_id": item["id"],
            "snapshot_date": TODAY,
            "region": region,
            "category_id": category_id,
            "title": sn.get("title", ""),
            "description": (sn.get("description") or "")[:1500],
            "tags": json.dumps(sn.get("tags", [])[:25], ensure_ascii=False),
            "channel_id": sn.get("channelId"),
            "channel_title": sn.get("channelTitle"),
            "channel_subs": None,
            "channel_age_days": None,
            "published_at": sn.get("publishedAt"),
            "duration_sec": iso_duration_to_sec(
                item.get("contentDetails", {}).get("duration", "")),
            "views": views,
            "likes": int(st.get("likeCount", 0) or 0),
            "comments": int(st.get("commentCount", 0) or 0),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })
    return rows


def enrich_channels(rows: list[dict]) -> None:
    """Bổ sung subscriber count + tuổi kênh. Sửa rows tại chỗ."""
    ids = sorted({r["channel_id"] for r in rows if r["channel_id"]})
    info: dict[str, tuple[int, int]] = {}
    now = datetime.now(timezone.utc)

    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        data = get("channels", {"part": "statistics,snippet", "id": ",".join(batch)})
        for ch in data.get("items", []):
            subs = int(ch.get("statistics", {}).get("subscriberCount", 0) or 0)
            created = ch.get("snippet", {}).get("publishedAt")
            age = 0
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age = max((now - dt).days, 0)
                except ValueError:
                    pass
            info[ch["id"]] = (subs, age)

    for r in rows:
        subs, age = info.get(r["channel_id"], (0, 0))
        r["channel_subs"] = subs
        r["channel_age_days"] = age


# --------------------------------------------------------------------------- #
# Autocomplete (không chính thức nhưng free)
# --------------------------------------------------------------------------- #
def fetch_suggestions(seed: str, region: str, lang: str) -> list[str]:
    try:
        r = requests.get(
            "https://suggestqueries.google.com/complete/search",
            params={"client": "firefox", "ds": "yt", "q": seed,
                    "hl": lang, "gl": region.lower()},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        return r.json()[1][:15]
    except Exception:
        return []


def derive_seeds(rows: list[dict], limit: int = 12) -> list[str]:
    """Lấy seed từ tag phổ biến nhất trong ngày nếu người dùng không tự cấu hình."""
    if config.SUGGEST_SEEDS:
        return config.SUGGEST_SEEDS
    freq: dict[str, int] = {}
    for r in rows:
        for t in json.loads(r["tags"]):
            t = t.lower().strip()
            if 3 <= len(t) <= 30:
                freq[t] = freq.get(t, 0) + 1
    return [k for k, _ in sorted(freq.items(), key=lambda x: -x[1])[:limit]]


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    if not API_KEY:
        raise SystemExit("Thiếu biến môi trường YOUTUBE_API_KEY")

    os.makedirs(config.OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.executescript(open("schema.sql", encoding="utf-8").read())

    all_rows: list[dict] = []
    for region in config.REGIONS:
        for cat in config.ACTIVE_CATEGORIES:
            got = fetch_trending(region, cat)
            all_rows.extend(got)
            print(f"{region}/{config.CATEGORIES[cat]['name']:<18} {len(got):>3} video")

    if not all_rows:
        raise SystemExit("Không lấy được dữ liệu nào.")

    print(f"\nBổ sung subscriber count cho {len({r['channel_id'] for r in all_rows})} kênh...")
    enrich_channels(all_rows)

    cols = list(all_rows[0].keys())
    conn.executemany(
        f"INSERT OR REPLACE INTO snapshots ({','.join(cols)}) "
        f"VALUES ({','.join('?' * len(cols))})",
        [tuple(r[c] for c in cols) for r in all_rows],
    )
    conn.commit()
    print(f"Đã lưu {len(all_rows)} dòng snapshot cho {TODAY}")

    # --- Autocomplete ---
    seeds = derive_seeds(all_rows)
    sug_rows = []
    for region in ("US", "GB", "DE", "FR", "CA"):
        lang = config.REGIONS[region]["lang"]
        for seed in seeds:
            for letter in ("", " a", " how", " best"):
                for rank, s in enumerate(fetch_suggestions(seed + letter, region, lang)):
                    sug_rows.append((TODAY, region, seed, s, rank))
                time.sleep(0.15)   # lịch sự với endpoint không chính thức

    conn.executemany(
        "INSERT OR REPLACE INTO suggestions VALUES (?,?,?,?,?)", sug_rows)
    conn.commit()
    print(f"Đã lưu {len(sug_rows)} gợi ý từ khóa")
    conn.close()


if __name__ == "__main__":
    main()
