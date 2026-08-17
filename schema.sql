-- Toàn bộ giá trị của hệ thống nằm ở chuỗi thời gian.
-- KHÔNG BAO GIỜ ghi đè snapshot cũ.

CREATE TABLE IF NOT EXISTS snapshots (
    video_id        TEXT    NOT NULL,
    snapshot_date   TEXT    NOT NULL,   -- YYYY-MM-DD (UTC)
    region          TEXT    NOT NULL,
    category_id     TEXT,
    title           TEXT,
    description     TEXT,
    tags            TEXT,               -- JSON array
    channel_id      TEXT,
    channel_title   TEXT,
    channel_subs    INTEGER,
    channel_age_days INTEGER,
    published_at    TEXT,
    duration_sec    INTEGER,
    views           INTEGER,
    likes           INTEGER,
    comments        INTEGER,
    fetched_at      TEXT,
    PRIMARY KEY (video_id, snapshot_date, region)
);

CREATE INDEX IF NOT EXISTS idx_snap_date    ON snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snap_video   ON snapshots(video_id);
CREATE INDEX IF NOT EXISTS idx_snap_channel ON snapshots(channel_id);

-- Điểm số tính lại mỗi ngày
CREATE TABLE IF NOT EXISTS scores (
    video_id        TEXT NOT NULL,
    snapshot_date   TEXT NOT NULL,
    region          TEXT NOT NULL,
    outlier_raw     REAL,
    velocity_raw    REAL,
    delta_raw       REAL,
    score           REAL,
    region_count    INTEGER,  -- video/chủ đề này xuất hiện ở bao nhiêu nước
    PRIMARY KEY (video_id, snapshot_date, region)
);

-- Kết quả phân cụm chủ đề của Claude
CREATE TABLE IF NOT EXISTS clusters (
    snapshot_date   TEXT NOT NULL,
    cluster_name    TEXT NOT NULL,
    cluster_name_vi TEXT,
    keywords        TEXT,   -- JSON array
    format          TEXT,
    language_dependency TEXT,  -- none | low | high
    production_cost TEXT,      -- low | medium | high
    saturation      TEXT,      -- low | medium | high
    regions         TEXT,      -- JSON array
    why_now         TEXT,
    angle           TEXT,      -- góc tiếp cận gợi ý cho kênh mới
    avg_score       REAL,
    video_ids       TEXT,      -- JSON array
    PRIMARY KEY (snapshot_date, cluster_name)
);

-- Từ khóa gợi ý từ YouTube Autocomplete
CREATE TABLE IF NOT EXISTS suggestions (
    snapshot_date   TEXT NOT NULL,
    region          TEXT NOT NULL,
    seed            TEXT NOT NULL,
    suggestion      TEXT NOT NULL,
    rank            INTEGER,
    PRIMARY KEY (snapshot_date, region, seed, suggestion)
);
