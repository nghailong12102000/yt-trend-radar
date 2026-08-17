"""Bước 1: tìm video LONG-FORM mới đăng đang được xem nhiều, tại 8 thị trường.

Khác với bản đầu tiên: bản này KHÔNG dùng chart=mostPopular nữa.

Lý do đổi: trang Trending khi lọc video dài chỉ còn lại livestream VOD và
kênh vài triệu sub. Chúng lên đó vì thương hiệu chứ không vì chủ đề, nên
một kênh mới không học được gì.

search.list cho phép hỏi thẳng câu đúng: "video dài nào ĐĂNG TRONG 7 NGÀY
QUA đang được xem nhiều nhất ở thị trường này". Đắt hơn 100 lần về quota
(100 unit/lần gọi thay vì 1) nên script tự đếm và dừng trước khi chạm trần.

Quy trình:
  1. search.list  -> lấy id video theo (quốc gia, category, thời lượng)
  2. videos.list  -> lấy view, thời lượng thật, category thật
  3. channels.list-> lấy subscriber
  4. lọc theo thời lượng / view / trần sub
  5. ghi snapshot
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

import config

API_KEY = os.environ.get("YOUTUBE_API_KEY")
BASE = "https://www.googleapis.com/youtube/v3"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

quota_used = 0


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


def get(endpoint: str, params: dict, cost: int) -> dict:
    """Gọi API và cộng dồn quota. Dừng hẳn nếu sắp vượt ngân sách."""
    global quota_used
    if quota_used + cost > config.DAILY_QUOTA_BUDGET:
        print(f"  ! Đã dùng {quota_used} unit, dừng để không vượt ngân sách "
              f"{config.DAILY_QUOTA_BUDGET}.", file=sys.stderr)
        return {}

    params["key"] = API_KEY
    for attempt in range(3):
        r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
        if r.status_code == 200:
            quota_used += cost
            return r.json()
        if r.status_code in (403, 429):
            if "quotaExceeded" in r.text:
                raise SystemExit(
                    f"Hết quota YouTube API. Đã dùng khoảng {quota_used} unit.\n"
                    "Quota reset lúc 14:00 giờ Việt Nam. Muốn giảm mức tiêu thụ, "
                    "bớt quốc gia hoặc category trong SEARCH_PLAN của config.py.")
            print(f"  ! {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return {}
        if r.status_code == 400:
            # tổ hợp tham số không hợp lệ với category/vùng này - bỏ qua
            print(f"  ! 400 (bỏ qua): {r.text[:120]}", file=sys.stderr)
            return {}
        time.sleep(2 ** attempt)
    return {}


# --------------------------------------------------------------------------- #
# Bước 1: tìm id video
# --------------------------------------------------------------------------- #
def search_ids(region: str, category_id: str, duration: str,
               published_after: str) -> list[str]:
    data = get("search", {
        "part": "id",
        "type": "video",
        "order": "viewCount",           # xem nhiều nhất, không phải liên quan nhất
        "publishedAfter": published_after,
        "regionCode": region,
        "relevanceLanguage": config.REGIONS[region]["lang"],
        "videoCategoryId": category_id,
        "videoDuration": duration,
        "maxResults": 50,
    }, cost=config.SEARCH_COST)

    return [it["id"]["videoId"] for it in data.get("items", [])
            if it.get("id", {}).get("videoId")]


# --------------------------------------------------------------------------- #
# Bước 2 + 3: lấy chi tiết
# --------------------------------------------------------------------------- #
def fetch_video_details(ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        data = get("videos", {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(ids[i:i + 50]),
        }, cost=config.LIST_COST)
        for item in data.get("items", []):
            out[item["id"]] = item
    return out


def fetch_channels(ids: list[str]) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    now = datetime.now(timezone.utc)
    for i in range(0, len(ids), 50):
        data = get("channels", {
            "part": "statistics,snippet",
            "id": ",".join(ids[i:i + 50]),
        }, cost=config.LIST_COST)
        for ch in data.get("items", []):
            subs = int(ch.get("statistics", {}).get("subscriberCount", 0) or 0)
            age = 0
            created = ch.get("snippet", {}).get("publishedAt")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age = max((now - dt).days, 0)
                except ValueError:
                    pass
            out[ch["id"]] = (subs, age)
    return out


# --------------------------------------------------------------------------- #
# Autocomplete (free, không chính thức)
# --------------------------------------------------------------------------- #
def fetch_suggestions(seed: str, region: str, lang: str) -> list[str]:
    try:
        r = requests.get(
            "https://suggestqueries.google.com/complete/search",
            params={"client": "firefox", "ds": "yt", "q": seed,
                    "hl": lang, "gl": region.lower()},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        return r.json()[1][:15] if r.status_code == 200 else []
    except Exception:
        return []


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    if not API_KEY:
        raise SystemExit("Thiếu biến môi trường YOUTUBE_API_KEY")

    os.makedirs(config.OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.executescript(open("schema.sql", encoding="utf-8").read())

    published_after = (datetime.now(timezone.utc)
                       - timedelta(days=config.LOOKBACK_DAYS)
                       ).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Tìm video đăng sau {published_after}\n")

    # --- Bước 1: gom id, nhớ video xuất hiện ở những vùng nào ---
    found: dict[str, set[str]] = {}          # video_id -> {region}
    for duration, regions in config.SEARCH_PLAN:
        for region in regions:
            for cat in config.SEARCH_CATEGORIES:
                ids = search_ids(region, cat, duration, published_after)
                for vid in ids:
                    found.setdefault(vid, set()).add(region)
                print(f"{region}/{duration:<6}/"
                      f"{config.CATEGORIES[cat]['name']:<16} {len(ids):>3} id"
                      f"   [quota {quota_used}]")

    if not found:
        raise SystemExit("Không tìm được video nào. Kiểm tra API key.")
    print(f"\nTổng {len(found)} video duy nhất. Đang lấy chi tiết...")

    # --- Bước 2: chi tiết video ---
    details = fetch_video_details(list(found))

    # --- Bước 3: subscriber ---
    ch_ids = sorted({v["snippet"]["channelId"] for v in details.values()})
    channels = fetch_channels(ch_ids)

    # --- Bước 4: lọc ---
    rows, drop_dur, drop_views, drop_subs = [], 0, 0, 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for vid, item in details.items():
        sn, st = item["snippet"], item.get("statistics", {})
        dur = iso_duration_to_sec(item.get("contentDetails", {}).get("duration", ""))
        views = int(st.get("viewCount", 0) or 0)
        subs, age = channels.get(sn["channelId"], (0, 0))

        if not (config.MIN_DURATION_SEC <= dur <= config.MAX_DURATION_SEC):
            drop_dur += 1
            continue
        if views < config.MIN_VIEWS:
            drop_views += 1
            continue
        if subs > config.MAX_SUBS_RESEARCH:
            drop_subs += 1
            continue

        for region in found[vid]:
            rows.append({
                "video_id": vid,
                "snapshot_date": TODAY,
                "region": region,
                "category_id": sn.get("categoryId"),
                "title": sn.get("title", ""),
                "description": (sn.get("description") or "")[:1500],
                "tags": json.dumps(sn.get("tags", [])[:25], ensure_ascii=False),
                "channel_id": sn.get("channelId"),
                "channel_title": sn.get("channelTitle"),
                "channel_subs": subs,
                "channel_age_days": age,
                "published_at": sn.get("publishedAt"),
                "duration_sec": dur,
                "views": views,
                "likes": int(st.get("likeCount", 0) or 0),
                "comments": int(st.get("commentCount", 0) or 0),
                "fetched_at": now_iso,
            })

    print(f"\nLoại bỏ: {drop_dur} do thời lượng, {drop_views} do ít view, "
          f"{drop_subs} do kênh quá lớn (>{config.MAX_SUBS_RESEARCH:,} sub)")

    if not rows:
        raise SystemExit(
            "Không còn video nào sau khi lọc.\n"
            "Thử nới LOOKBACK_DAYS, hạ MIN_VIEWS, hoặc nới MAX_DURATION_SEC "
            "trong config.py.")

    cols = list(rows[0].keys())
    conn.executemany(
        f"INSERT OR REPLACE INTO snapshots ({','.join(cols)}) "
        f"VALUES ({','.join('?' * len(cols))})",
        [tuple(r[c] for c in cols) for r in rows])
    conn.commit()

    uniq = len({r["video_id"] for r in rows})
    print(f"Đã lưu {len(rows)} dòng / {uniq} video duy nhất cho {TODAY}")
    if uniq < 40:
        print("  ! Mẫu nhỏ. Cân nhắc tăng LOOKBACK_DAYS hoặc thêm category.")

    # --- Autocomplete ---
    freq: dict[str, int] = {}
    for r in rows:
        for t in json.loads(r["tags"]):
            t = t.lower().strip()
            if 3 <= len(t) <= 30:
                freq[t] = freq.get(t, 0) + 1
    seeds = config.SUGGEST_SEEDS or [
        k for k, _ in sorted(freq.items(), key=lambda x: -x[1])[:12]]

    sug = []
    for region in ("US", "GB", "DE"):
        lang = config.REGIONS[region]["lang"]
        for seed in seeds:
            for suffix in ("", " how", " best"):
                for rank, s in enumerate(fetch_suggestions(seed + suffix, region, lang)):
                    sug.append((TODAY, region, seed, s, rank))
                time.sleep(0.15)

    conn.executemany("INSERT OR REPLACE INTO suggestions VALUES (?,?,?,?,?)", sug)
    conn.commit()
    print(f"Đã lưu {len(sug)} gợi ý từ khóa")
    print(f"\nTổng quota đã dùng: {quota_used} / 10.000")
    conn.close()


if __name__ == "__main__":
    main()
