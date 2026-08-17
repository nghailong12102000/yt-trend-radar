# YouTube Trend Radar

Quét chủ đề đang lên tại 16 thị trường Bắc Mỹ + Tây Âu mỗi ngày, chấm điểm theo
tiêu chí của **một kênh mới**, xuất ra Google Sheets.

Chỉ cần **một API key duy nhất** (YouTube Data API, miễn phí). Không dùng
Claude API, không dùng service account, không tốn chi phí hạ tầng.

## Điểm khác biệt so với việc tự xem trang Trending

Trang Trending trả lời câu hỏi *"video nào nhiều view nhất"*. Đó là câu hỏi sai
với một kênh chưa có audience — nó luôn dẫn tới Music, Sports và các kênh media
lớn mà bạn không cạnh tranh nổi.

Hệ thống này trả lời *"chủ đề nào thắng bất kể ai làm"*, bằng cách ưu tiên
**outlier factor = views ÷ subscribers**. Một video 400k view từ kênh 8k sub
đáng học hơn nhiều so với 4M view từ kênh 12M sub.

| Chỉ số | Trọng số | Bắt được điều gì |
|---|---|---|
| Outlier | 45% | Chủ đề thắng, không phải thương hiệu thắng |
| Velocity | 25% | Video đang tăng nhanh |
| Delta ngày | 20% | Còn đang lên hay đã nguội |
| Underdog | 10% | Kênh nhỏ lọt được trending |

Sau đó nhân với hệ số **RPM theo quốc gia** (Na Uy 0.90, Mỹ 1.00, Ba Lan 0.30 —
cùng 1 triệu view nhưng doanh thu chênh 3 lần) và **trọng số category**
(Music/Sports/News để 0.0 vì kênh mới không nên đụng vào).

## Cài đặt

1. Fork repo này. **Để chế độ Public** thì Google Sheets mới đọc được CSV.
   (Muốn giữ Private thì xem phần Gist trong SHEET_SETUP.md.)
2. Lấy **YouTube Data API v3 key** tại [console.cloud.google.com](https://console.cloud.google.com)
   → tạo project → Enable APIs → YouTube Data API v3 → Credentials → API key.
   Quota free 10.000 unit/ngày; workflow này dùng ~240.
3. Settings → Secrets and variables → Actions → thêm secret `YOUTUBE_API_KEY`.
4. Tab Actions → Daily Trend Radar → **Run workflow**.
5. Nối vào Google Sheets: làm theo [SHEET_SETUP.md](SHEET_SETUP.md).

Chạy local:

```bash
pip install -r requirements.txt
export YOUTUBE_API_KEY="AIza..."
python fetch.py && python score.py && python keywords.py && python export_csv.py
```

## Kết quả

- `data/radar.db` — toàn bộ lịch sử snapshot. **Đừng xóa và đừng gitignore file này**:
  chỉ số delta cần dữ liệu hôm qua để so sánh. Ngày đầu tiên chạy sẽ chưa có delta,
  đó là bình thường.
- `data/latest.csv` — top 300 video hôm nay, ghi đè mỗi ngày.
- `data/history.csv` — top 50/ngày, nối thêm.
- `data/keywords.csv` — từ khóa nổi bật hôm nay, ghi đè.
- `data/keywords_history.csv` — top 40 từ khóa/ngày, nối thêm.

Bốn file CSV này có **đường dẫn cố định** để công thức `=IMPORTDATA()` trong
Google Sheets luôn trỏ đúng chỗ. Đừng đổi tên file.

## Sau 30 ngày nên làm gì

Dữ liệu tích lũy mới là phần có giá trị. Khi đã có ~1 tháng snapshot:

- Xem tab Dashboard, bảng **từ khóa lặp lại nhiều ngày** — đó là trend thật,
  khác với spike một ngày do một sự kiện.
- So sánh cột `regions` để tìm chủ đề đã nổ ở Mỹ nhưng chưa ở Đức/Pháp — độ trễ
  giữa các thị trường thường 1-3 tuần và đó là cửa sổ để bạn vào trước.
- Thay hệ số `rpm` trong `config.py` bằng RPM thật từ YouTube Analytics của bạn.

## Tinh chỉnh

Mọi thứ nằm trong `config.py`: thêm/bớt quốc gia, bật lại category đã tắt,
đổi trọng số, chỉnh ngưỡng `MIN_VIEWS`.

Nếu từ khóa ra nhiều rác, mở `keywords.py` và bổ sung vào tập `STOP`.

## Các file tùy chọn, không chạy trong workflow

Giữ lại phòng khi bạn đổi ý, nhưng mặc định không được gọi tới:

| File | Làm gì | Cần thêm |
|---|---|---|
| `cluster.py` | Gom video thành **cụm chủ đề** kèm đánh giá độ phụ thuộc ngôn ngữ và góc tiếp cận cho kênh mới | `pip install anthropic`, secret `ANTHROPIC_API_KEY` |
| `export_sheets.py` | Đẩy thẳng vào Sheets qua service account | `pip install gspread google-auth`, file JSON |
| `export_sheets_webapp.py` + `apps_script/Code.gs` | Đẩy vào Sheets qua Apps Script | Deploy web app, `GAS_URL` + `GAS_TOKEN` |
| `push_gist.py` | Đẩy CSV lên Gist để giữ repo private | `GIST_ID` + `GIST_TOKEN` |

`keywords.py` (chạy mặc định) chỉ cho biết **từ nào đang nóng**. Nó không nói
được chủ đề đó có tái tạo được với một kênh mới hay không, cũng không đánh giá
được việc bạn có cần giọng đọc bản ngữ hay không. Phần đó là việc của
`cluster.py`. Nếu sau vài tuần bạn thấy cần, bật lại nó tốn khoảng vài cent mỗi ngày.

## Giới hạn cần biết

- `chart=mostPopular` chỉ trả tối đa 50 video/category/region và một số category
  trả rỗng ở một số nước — đó là hành vi của API, không phải lỗi.
- Endpoint autocomplete (`suggestqueries.google.com`) không phải API chính thức.
  Nó có thể đổi format hoặc chặn bất cứ lúc nào; script đã bọc try/except để
  không làm hỏng cả pipeline nếu điều đó xảy ra.
- Phân tích từ khóa dựa trên đếm tần suất, nên nó thiên vị từ tiếng Anh và
  có thể bỏ sót chủ đề được diễn đạt bằng nhiều cách khác nhau.
- Hệ thống này tìm **chủ đề**, không tìm **niche**. Chạy 2-4 tuần để quan sát rồi
  mới chọn hướng kênh, đừng đổi chủ đề theo từng ngày.
