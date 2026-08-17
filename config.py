"""Cấu hình trung tâm cho YT Trend Radar."""

# ---------------------------------------------------------------------------
# THỊ TRƯỜNG
# rpm: hệ số doanh thu tương đối, lấy mốc US = 1.00.
# Con số này là ước lượng thô từ dữ liệu ngành, hãy thay bằng số thật
# trong YouTube Analytics của bạn sau ~90 ngày chạy kênh.
# ---------------------------------------------------------------------------
REGIONS = {
    "US": {"name": "United States", "rpm": 1.00, "lang": "en"},
    "CA": {"name": "Canada",        "rpm": 0.80, "lang": "en"},
    "GB": {"name": "United Kingdom","rpm": 0.85, "lang": "en"},
    "IE": {"name": "Ireland",       "rpm": 0.70, "lang": "en"},
    "AU": {"name": "Australia",     "rpm": 0.85, "lang": "en"},
    "DE": {"name": "Germany",       "rpm": 0.75, "lang": "de"},
    "CH": {"name": "Switzerland",   "rpm": 0.85, "lang": "de"},
    "AT": {"name": "Austria",       "rpm": 0.65, "lang": "de"},
    "NO": {"name": "Norway",        "rpm": 0.90, "lang": "no"},
    "SE": {"name": "Sweden",        "rpm": 0.75, "lang": "sv"},
    "DK": {"name": "Denmark",       "rpm": 0.80, "lang": "da"},
    "NL": {"name": "Netherlands",   "rpm": 0.70, "lang": "nl"},
    "FR": {"name": "France",        "rpm": 0.55, "lang": "fr"},
    "IT": {"name": "Italy",         "rpm": 0.35, "lang": "it"},
    "ES": {"name": "Spain",         "rpm": 0.35, "lang": "es"},
    "PL": {"name": "Poland",        "rpm": 0.30, "lang": "pl"},
}

# ---------------------------------------------------------------------------
# CATEGORY
# weight: mức độ đáng quan tâm với một kênh mới, không phải độ phổ biến.
# Music/Sports/News để 0 vì kênh nhỏ gần như không cạnh tranh nổi và
# dính bản quyền. Bật lại nếu bạn có lý do riêng.
# ---------------------------------------------------------------------------
CATEGORIES = {
    "1":  {"name": "Film & Animation",  "weight": 0.8},
    "2":  {"name": "Autos & Vehicles",  "weight": 0.9},
    "10": {"name": "Music",             "weight": 0.0},
    "15": {"name": "Pets & Animals",    "weight": 1.0},
    "17": {"name": "Sports",            "weight": 0.0},
    "19": {"name": "Travel & Events",   "weight": 0.9},
    "20": {"name": "Gaming",            "weight": 0.9},
    "22": {"name": "People & Blogs",    "weight": 0.7},
    "23": {"name": "Comedy",            "weight": 0.8},
    "24": {"name": "Entertainment",     "weight": 0.7},
    "25": {"name": "News & Politics",   "weight": 0.0},
    "26": {"name": "Howto & Style",     "weight": 1.0},
    "27": {"name": "Education",         "weight": 1.0},
    "28": {"name": "Science & Tech",    "weight": 1.0},
}

# Chỉ lấy category có weight > 0 để tiết kiệm quota
ACTIVE_CATEGORIES = [k for k, v in CATEGORIES.items() if v["weight"] > 0]

# ---------------------------------------------------------------------------
# TRỌNG SỐ CHẤM ĐIỂM
# ---------------------------------------------------------------------------
WEIGHTS = {
    "outlier":     0.45,  # views / subscribers -> chủ đề thắng, không phải brand thắng
    "velocity":    0.25,  # views / giờ kể từ khi publish
    "delta":       0.20,  # tăng trưởng view so với snapshot hôm qua
    "underdog":    0.10,  # kênh càng nhỏ mà lên được trending càng đáng chú ý
}

# ---------------------------------------------------------------------------
# LỌC THEO THỜI LƯỢNG — quan trọng nhất với kênh long-form
# Trang trending hiện bị Shorts chiếm gần hết. Shorts và long-form là hai
# cuộc chơi khác nhau: RPM chênh nhau khoảng 10-20 lần, format khác, cách
# phân phối khác. Lọc bỏ Shorts thì bảng xếp hạng mới nói đúng chuyện.
#
# Shorts tối đa 180 giây. Đặt ngưỡng ngay trên mốc đó.
# Muốn nghiên cứu Shorts thay vì long-form: đặt MIN_DURATION_SEC = 0
# và MAX_DURATION_SEC = 180.
# ---------------------------------------------------------------------------
MIN_DURATION_SEC = 181
MAX_DURATION_SEC = 100_000        # không giới hạn trên

# Mốc 8 phút: video từ đây trở lên được chèn quảng cáo giữa bài, tức doanh
# thu trên mỗi 1000 view cao hơn đáng kể. Thưởng điểm cho nhóm này.
MIDROLL_SEC = 480
MIDROLL_BONUS = 1.15

# Ngưỡng lọc
MIN_VIEWS = 20_000        # bỏ video quá nhỏ, nhiễu
MAX_SUBS_FOR_UNDERDOG = 250_000
MIN_HOURS_SINCE_PUBLISH = 6   # tránh chia cho số quá nhỏ làm velocity nổ

# Seed keyword để mở rộng qua YouTube Autocomplete (bước 2).
# Để rỗng thì script tự lấy từ khóa từ top video của ngày.
SUGGEST_SEEDS = []
SUGGEST_ALPHABET = "abcdefghijklmnopqrstuvwxyz"

DB_PATH = "data/radar.db"
OUT_DIR = "data"
