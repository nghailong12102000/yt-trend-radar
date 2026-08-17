"""Bước 2: chấm điểm.

Triết lý: view thô vô nghĩa với kênh mới. Cái đáng đo là
  - outlier : view / subscriber -> chủ đề thắng chứ không phải thương hiệu thắng
  - velocity: view / giờ         -> tốc độ, bắt video đang nổi
  - delta   : view tăng thêm/giờ so với snapshot hôm qua -> còn đang tăng hay đã nguội
  - underdog: kênh càng nhỏ mà lọt trending càng đáng học
"""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone

import config

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def normalize(values: list[float]) -> list[float]:
    """Log-scale rồi min-max về [0,1]. Log để một video 50M view
    không nuốt chửng toàn bộ thang điểm."""
    logs = [math.log10(max(v, 0) + 1) for v in values]
    lo, hi = min(logs), max(logs)
    if hi - lo < 1e-9:
        return [0.5] * len(logs)
    return [(x - lo) / (hi - lo) for x in logs]


def main() -> None:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT * FROM snapshots WHERE snapshot_date = ?", (TODAY,)
    ).fetchall()
    if not rows:
        raise SystemExit(f"Chưa có snapshot cho {TODAY}. Chạy fetch.py trước.")

    # view của cùng video ở lần snapshot gần nhất trước đó
    prev = {
        r["video_id"]: (r["views"], r["snapshot_date"])
        for r in conn.execute(
            """SELECT video_id, views, snapshot_date FROM snapshots
               WHERE snapshot_date < ?
               GROUP BY video_id HAVING MAX(snapshot_date)""", (TODAY,))
    }

    # video xuất hiện ở bao nhiêu quốc gia hôm nay -> tín hiệu chủ đề xuyên biên giới
    region_count: dict[str, int] = {}
    for r in rows:
        region_count[r["video_id"]] = region_count.get(r["video_id"], 0) + 1

    now = datetime.now(timezone.utc)
    outliers, velocities, deltas, underdogs, meta = [], [], [], [], []

    for r in rows:
        subs = max(r["channel_subs"] or 0, 1000)
        views = r["views"]

        try:
            pub = datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
            hours = max((now - pub).total_seconds() / 3600, config.MIN_HOURS_SINCE_PUBLISH)
        except Exception:
            hours = 24.0

        outlier = views / subs
        velocity = views / hours

        prev_views, prev_date = prev.get(r["video_id"], (None, None))
        if prev_views is not None:
            try:
                gap_h = max(
                    (datetime.fromisoformat(TODAY) - datetime.fromisoformat(prev_date))
                    .total_seconds() / 3600, 1)
            except Exception:
                gap_h = 24
            delta = max(views - prev_views, 0) / gap_h
        else:
            # video mới xuất hiện lần đầu -> dùng velocity làm proxy, chiết khấu
            delta = velocity * 0.6

        underdog = 1.0 if subs <= config.MAX_SUBS_FOR_UNDERDOG else \
            config.MAX_SUBS_FOR_UNDERDOG / subs

        outliers.append(outlier)
        velocities.append(velocity)
        deltas.append(delta)
        underdogs.append(underdog)
        meta.append(r)

    n_out, n_vel, n_del = normalize(outliers), normalize(velocities), normalize(deltas)

    out_rows = []
    for i, r in enumerate(meta):
        w = config.WEIGHTS
        base = (w["outlier"] * n_out[i]
                + w["velocity"] * n_vel[i]
                + w["delta"] * n_del[i]
                + w["underdog"] * underdogs[i])

        rpm = config.REGIONS.get(r["region"], {}).get("rpm", 0.5)
        cat_w = config.CATEGORIES.get(str(r["category_id"]), {}).get("weight", 0.5)
        # bonus nhẹ cho chủ đề xuất hiện ở nhiều nước
        spread = 1 + 0.06 * (region_count[r["video_id"]] - 1)

        score = round(base * rpm * cat_w * spread * 100, 2)

        out_rows.append((r["video_id"], TODAY, r["region"],
                         round(outliers[i], 4), round(velocities[i], 2),
                         round(deltas[i], 2), score, region_count[r["video_id"]]))

    conn.executemany(
        "INSERT OR REPLACE INTO scores VALUES (?,?,?,?,?,?,?,?)", out_rows)
    conn.commit()

    top = conn.execute("""
        SELECT s.title, s.channel_title, s.channel_subs, s.views,
               s.region, sc.score, sc.outlier_raw, sc.region_count
        FROM scores sc JOIN snapshots s
          ON s.video_id = sc.video_id AND s.snapshot_date = sc.snapshot_date
         AND s.region = sc.region
        WHERE sc.snapshot_date = ?
        ORDER BY sc.score DESC LIMIT 20""", (TODAY,)).fetchall()

    print(f"\n=== TOP 20 NGÀY {TODAY} ===")
    for t in top:
        print(f"{t['score']:>6.1f} | {t['region']} | x{t['outlier_raw']:>7.1f} | "
              f"{t['region_count']} nước | {t['title'][:60]}")
        print(f"       {t['channel_title']} · {t['channel_subs']:,} subs · "
              f"{t['views']:,} views")
    conn.close()


if __name__ == "__main__":
    main()
