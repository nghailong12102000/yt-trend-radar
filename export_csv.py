"""Bước 4 (phương án C): xuất CSV ra đường dẫn CỐ ĐỊNH để Google Sheets tự kéo về.

Không service account, không Apps Script, không token, không đụng Google Cloud.
Google Sheets dùng =IMPORTDATA() trỏ tới file CSV trên GitHub và tự cập nhật.

Xuất 3 file, tên KHÔNG chứa ngày để công thức IMPORTDATA luôn trỏ đúng chỗ:
  data/latest.csv   - top video hôm nay, GHI ĐÈ mỗi ngày
  data/history.csv  - top 50/ngày, NỐI THÊM (để soi chủ đề lặp lại)

Từ khóa được xuất riêng bởi keywords.py.

Lưu ý về định dạng số: file ghi bằng UTF-8 KHÔNG BOM và dùng dấu chấm thập phân.
Google Sheet của bạn phải để locale United States (File > Settings > Locale),
nếu không Sheets sẽ hiểu sai số thập phân. Điểm số được làm tròn thành số
nguyên để giảm rủi ro này.
"""
from __future__ import annotations

import csv
import os
import sqlite3
from datetime import datetime, timezone

import config

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

LATEST_HEADER = ["score", "outlier", "mins", "top_region", "n_regions", "regions",
                 "title", "channel", "subs", "views", "category", "url"]
HISTORY_HEADER = ["date", "score", "outlier", "region", "title", "channel", "url"]


def write_replace(path: str, header: list[str], rows: list[list]) -> None:
    """Ghi đè toàn bộ file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(header)
        w.writerows(rows)


def write_append(path: str, header: list[str], rows: list[list],
                 dedupe_on_date: bool = True) -> int:
    """Nối thêm vào cuối file, bỏ qua nếu ngày hôm nay đã có sẵn.

    Chống trùng khi workflow bị chạy lại hai lần trong cùng một ngày.
    """
    existing: list[list[str]] = []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            existing = list(csv.reader(f))[1:]   # bỏ header

    if dedupe_on_date:
        existing = [r for r in existing if r and r[0] != TODAY]

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(header)
        w.writerows(existing)
        w.writerows(rows)
    return len(existing) + len(rows)


def clean(text: str | None, limit: int = 300) -> str:
    """Bỏ xuống dòng và ký tự làm vỡ CSV khi Sheets đọc."""
    if not text:
        return ""
    return " ".join(str(text).split())[:limit]


def main() -> None:
    os.makedirs(config.OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Lấy dư rồi mới khử trùng lặp, để đủ 300 video DUY NHẤT chứ không phải
    # 300 dòng (mỗi video xuất hiện ở 8-16 nước nên 300 dòng chỉ ra ~60 video).
    rows = conn.execute("""
        SELECT s.video_id, s.title, s.channel_title, s.channel_subs, s.views,
               s.region, s.category_id, s.duration_sec,
               sc.score, sc.outlier_raw, sc.region_count
        FROM scores sc JOIN snapshots s
          ON s.video_id = sc.video_id AND s.snapshot_date = sc.snapshot_date
         AND s.region = sc.region
        WHERE sc.snapshot_date = ?
        ORDER BY sc.score DESC LIMIT 4000""", (TODAY,)).fetchall()

    if not rows:
        raise SystemExit(f"Chưa có điểm cho {TODAY}. Chạy fetch.py và score.py trước.")

    # ---------------- latest.csv : ghi đè ----------------
    # Gom TẤT CẢ quốc gia của mỗi video. Nếu chỉ giữ dòng điểm cao nhất thì
    # US và NO luôn thắng (do hệ số RPM), và bảng mất hết tính đa quốc gia.
    all_regions: dict[str, list[str]] = {}
    for r in rows:
        all_regions.setdefault(r["video_id"], []).append(r["region"])

    seen, latest = set(), []
    for r in rows:
        if r["video_id"] in seen:
            continue
        seen.add(r["video_id"])
        regs = sorted(set(all_regions[r["video_id"]]))
        latest.append([
            round(r["score"]),
            round(r["outlier_raw"], 1),
            round((r["duration_sec"] or 0) / 60, 1),
            r["region"],
            len(regs),
            ", ".join(regs),
            clean(r["title"], 120),
            clean(r["channel_title"], 60),
            r["channel_subs"] or 0,
            r["views"] or 0,
            config.CATEGORIES.get(str(r["category_id"]), {}).get("name", ""),
            f"https://youtu.be/{r['video_id']}",
        ])
        if len(latest) >= 300:
            break
    write_replace(f"{config.OUT_DIR}/latest.csv", LATEST_HEADER, latest)
    print(f"latest.csv   : {len(latest)} dòng (ghi đè)")

    # ---------------- history.csv : nối thêm ----------------
    hist = [[TODAY, row[0], row[1], row[3], row[6], row[7], row[11]]
            for row in latest[:50]]
    total = write_append(f"{config.OUT_DIR}/history.csv", HISTORY_HEADER, hist)
    print(f"history.csv  : +{len(hist)} dòng (tổng {total})")

    conn.close()


if __name__ == "__main__":
    main()
