"""Bước 3 (thay cho cluster.py): rút từ khóa nổi bật, chạy hoàn toàn local.

Không gọi API nào. Gom tiêu đề + tag của top video trong ngày, tách thành
cụm 1 từ và 2 từ, rồi xếp hạng theo tổng điểm của các video chứa từ đó,
có thưởng thêm cho từ xuất hiện ở nhiều quốc gia.

Xuất 2 file:
  data/keywords.csv         - top từ khóa hôm nay, GHI ĐÈ
  data/keywords_history.csv - top 40/ngày, NỐI THÊM (để soi từ lặp lại)

Đây KHÔNG phải phân cụm chủ đề. Nó cho bạn biết từ nào đang nóng, nhưng
không nói được chủ đề đó có tái tạo được với kênh mới hay không. Phần đánh
giá đó nằm ở cluster.py (cần Claude API), hiện không chạy trong workflow.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

import config

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
TOP_TERMS = 100
HISTORY_TERMS = 40

HEADER = ["term", "n_videos", "n_regions", "regions", "weight",
          "max_outlier", "example_title", "example_url"]
HIST_HEADER = ["date", "term", "n_videos", "n_regions", "weight"]

# Stopword đa ngôn ngữ. Trending đa quốc gia nên tiêu đề lẫn nhiều thứ tiếng.
STOP = set("""
the a an and or but of to in on at for with from by as is are was were be been
this that these those it its his her their your our my me you he she they we
what how why when where who which not no yes all any can will just now new get
got make made how's don't dont vs feat ft official video music trailer full
episode part shorts live now best top most first last day week year time
und der die das den dem ein eine einer ist sind war mit von zu im am für auf
nicht auch wie was wer wo sich es sie ich du wir ihr mehr
le la les des du de et un une est sont dans pour sur avec par ce cette qui que
pas plus tout tous mais ou nous vous ils elles je tu il elle
el los las un una es son en para con por su sus lo que no si mas pero como
il lo gli un una di da del della che non per con sul come piu
de het een van is zijn in op voor met dat niet ook maar aan te
och att en ett som det den för med av inte har
i w z na do nie to jest się że po za od
""".split())

WORD_RE = re.compile(r"[a-zA-ZÀ-ÿĀ-ſ0-9']+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    toks = [t.lower() for t in WORD_RE.findall(text or "")]
    return [t for t in toks
            if len(t) >= 3 and t not in STOP and not t.isdigit()]


def terms_from(title: str, tags: list[str]) -> set[str]:
    """Sinh cụm 1 từ và 2 từ. Dùng set để một video chỉ tính 1 lần mỗi từ."""
    out: set[str] = set()
    toks = tokenize(title)
    out.update(toks)
    out.update(f"{a} {b}" for a, b in zip(toks, toks[1:]))
    for tag in tags[:12]:
        tt = tokenize(tag)
        if 1 <= len(tt) <= 3:
            out.add(" ".join(tt))
    return {t for t in out if len(t) >= 3}


def write_append(path: str, header: list[str], rows: list[list]) -> int:
    existing: list[list[str]] = []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            existing = [r for r in list(csv.reader(f))[1:] if r and r[0] != TODAY]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(existing)
        w.writerows(rows)
    return len(existing) + len(rows)


def main() -> None:
    os.makedirs(config.OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT s.video_id, s.title, s.tags, s.region,
               sc.score, sc.outlier_raw
        FROM scores sc JOIN snapshots s
          ON s.video_id = sc.video_id AND s.snapshot_date = sc.snapshot_date
         AND s.region = sc.region
        WHERE sc.snapshot_date = ?
        ORDER BY sc.score DESC LIMIT 400""", (TODAY,)).fetchall()

    if not rows:
        raise SystemExit(f"Chưa có điểm cho {TODAY}. Chạy fetch.py và score.py trước.")

    videos: dict[str, list] = defaultdict(set)
    weight: dict[str, float] = defaultdict(float)
    regions: dict[str, set] = defaultdict(set)
    outlier: dict[str, float] = defaultdict(float)
    example: dict[str, tuple] = {}

    for r in rows:
        try:
            tags = json.loads(r["tags"] or "[]")
        except ValueError:
            tags = []
        for term in terms_from(r["title"], tags):
            videos[term].add(r["video_id"])
            weight[term] += r["score"]
            regions[term].add(r["region"])
            outlier[term] = max(outlier[term], r["outlier_raw"])
            if term not in example:
                example[term] = (r["title"], r["video_id"])

    # Bỏ từ chỉ xuất hiện ở 1 video: là tên riêng hoặc nhiễu, không phải xu hướng
    cands = [t for t in videos if len(videos[t]) >= 2]

    def rank(t: str) -> float:
        # thưởng cho từ lan ra nhiều nước, và cho cụm 2 từ (cụ thể hơn)
        spread = 1 + math.log(len(regions[t]) + 1)
        specific = 1.25 if " " in t else 1.0
        return weight[t] * spread * specific

    cands.sort(key=rank, reverse=True)

    # Bỏ cụm 1 từ đã nằm trong cụm 2 từ xếp hạng cao hơn
    kept, covered = [], set()
    for t in cands:
        if " " not in t and t in covered:
            continue
        kept.append(t)
        if " " in t:
            covered.update(t.split())
        if len(kept) >= TOP_TERMS:
            break

    out_rows = []
    for t in kept:
        title, vid = example[t]
        out_rows.append([
            t, len(videos[t]), len(regions[t]),
            ", ".join(sorted(regions[t])),
            round(rank(t)),
            round(outlier[t], 1),
            " ".join(str(title).split())[:110],
            f"https://youtu.be/{vid}",
        ])

    with open(f"{config.OUT_DIR}/keywords.csv", "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(out_rows)
    print(f"keywords.csv         : {len(out_rows)} từ khóa (ghi đè)")

    hist = [[TODAY, r[0], r[1], r[2], r[4]] for r in out_rows[:HISTORY_TERMS]]
    total = write_append(f"{config.OUT_DIR}/keywords_history.csv", HIST_HEADER, hist)
    print(f"keywords_history.csv : +{len(hist)} dòng (tổng {total})")

    print("\nTop 15 hôm nay:")
    for r in out_rows[:15]:
        print(f"  {r[4]:>6} | {r[2]} nước | {r[1]} video | {r[0]}")

    conn.close()


if __name__ == "__main__":
    main()
