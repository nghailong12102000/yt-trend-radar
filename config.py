"""Cấu hình trung tâm cho YT Trend Radar."""

# ---------------------------------------------------------------------------
# THỊ TRƯỜNG
# rpm: hệ số doanh thu tương đối, lấy mốc US = 1.00.
# Con số này là ước lượng thô từ dữ liệu ngành, hãy thay bằng số thật
# trong YouTube Analytics của bạn sau ~90 ngày chạy kênh.
# ---------------------------------------------------------------------------
REGIONS = {
    "US": {"name": "United States", "rpm": 1.00, "lang": "en"},
    "GB": {"name": "United Kingdom","rpm": 0.85, "lang": "en"},
    "CA": {"name": "Canada",        "rpm": 0.80, "lang": "en"},
    "AU": {"name": "Australia",     "rpm": 0.85, "lang": "en"},
    "DE": {"name": "Germany",       "rpm": 0.75, "lang": "de"},
    "NO": {"name": "Norway",        "rpm": 0.90, "lang": "no"},
    "NL": {"name": "Netherlands",   "rpm": 0.70, "lang": "nl"},
    "SE": {"name": "Sweden",        "rpm": 0.75, "lang": "sv"},
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

# ---------------------------------------------------------------------------
# KẾ HOẠCH TÌM KIẾM
# fetch.py dùng search.list thay cho chart=mostPopular. Lý do: trang Trending
# với video dài chỉ toàn livestream và kênh triệu sub, không dùng được cho
# một kênh mới. search.list cho phép hỏi thẳng: "video dài nào MỚI ĐĂNG gần
# đây đang được xem nhiều nhất".
#
# CHI PHÍ: search.list tốn 100 unit/lần gọi (mostPopular chỉ tốn 1).
# Quota miễn phí là 10.000/ngày nên phải đếm cẩn thận.
#
# videoDuration của YouTube:
#   medium = 4-20 phút   (vùng vàng của long-form, có quảng cáo giữa bài)
#   long   = trên 20 phút
# ---------------------------------------------------------------------------
SEARCH_CATEGORIES = ["26", "28", "2", "15", "27"]   # Howto, Sci&Tech, Autos, Pets, Education

SEARCH_PLAN = [
    # (videoDuration, danh sách quốc gia)
    ("medium", ["US", "GB", "CA", "AU", "DE", "NO", "NL", "SE"]),
    ("long",   ["US", "GB", "DE"]),
]

LOOKBACK_DAYS = 7          # chỉ tìm video đăng trong 7 ngày gần nhất
DAILY_QUOTA_BUDGET = 8_500 # tự dừng trước khi chạm trần 10.000
SEARCH_COST = 100
LIST_COST = 1

ACTIVE_CATEGORIES = SEARCH_CATEGORIES

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
MIN_DURATION_SEC = 300      # 5 phút. Dưới mức này không phải long-form.
MAX_DURATION_SEC = 5_400    # 90 phút. Trên mức này gần như chắc chắn là
                            # livestream VOD - không phải nội dung tái tạo được.

# Mốc 8 phút: video từ đây trở lên được chèn quảng cáo giữa bài, tức doanh
# thu trên mỗi 1000 view cao hơn đáng kể. Thưởng điểm cho nhóm này.
MIDROLL_SEC = 480
MIDROLL_BONUS = 1.15

# Ngưỡng lọc
MIN_VIEWS = 20_000        # bỏ video quá nhỏ, nhiễu

# Bỏ qua kênh quá lớn. Video của MrBeast hay MKBHD lên top vì thương hiệu,
# không vì chủ đề - giữ lại chỉ làm lệch thang điểm và không học được gì.
MAX_SUBS_RESEARCH = 5_000_000
MAX_SUBS_FOR_UNDERDOG = 250_000
MIN_HOURS_SINCE_PUBLISH = 6   # tránh chia cho số quá nhỏ làm velocity nổ

# Seed keyword để mở rộng qua YouTube Autocomplete (bước 2).
# Để rỗng thì script tự lấy từ khóa từ top video của ngày.
SUGGEST_SEEDS = []
SUGGEST_ALPHABET = "abcdefghijklmnopqrstuvwxyz"

DB_PATH = "data/radar.db"
OUT_DIR = "data"
