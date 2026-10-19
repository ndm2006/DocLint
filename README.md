# DocLint

Web chuẩn hóa trình bày DOCX bằng Python/FastAPI và OpenXML, có giao diện tiếng Việt. Luồng chính: **tải lên → chọn mẫu → chỉnh thuộc tính trình bày → đối chiếu toàn vẹn → xem báo cáo → tải bản riêng**.

Bản triển khai này theo định hướng báo cáo tuần 5: việc sửa bố cục không được làm thay đổi nội dung. Không cần API key, AI, cơ sở dữ liệu hoặc dịch vụ xử lý tài liệu bên ngoài.

## Chạy để phát triển

Yêu cầu Python 3.12 (đã kiểm thử), các phụ thuộc ghim phiên bản trong `DocLint/requirements.txt`. Tệp requirements gốc là UTF-16; pip đọc trực tiếp được, không cần chuyển mã.

Từ thư mục gốc repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r DocLint/requirements-dev.txt
cd DocLint
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --no-access-log
```

Mở ứng dụng trên cổng 8000 qua công cụ chuyển tiếp cổng của môi trường chạy. Không có bước build frontend. Nếu chỉ chạy ứng dụng, có thể cài `requirements.txt` thay cho `requirements-dev.txt`.

Trong môi trường cloud đã chuẩn bị, dùng `/workspace/.venvs/doclint/bin/python` thay cho `python`. Mỗi tác vụ cloud đã được cô lập; sử dụng checkout hiện có, không cần tạo Git worktree.

## Quy tắc định dạng

| Mẫu | Thân bài | Trang dọc |
| --- | --- | --- |
| HUST | Times New Roman 13 pt, giãn dòng 1,5; cách trước/sau 6 pt | A4, trái 3 cm, các lề còn lại 2 cm |
| Báo cáo gọn gàng | Calibri 12 pt, giãn dòng 1,2; sau đoạn 8 pt | A4, trái/phải 2,5 cm, trên/dưới 2 cm |

Mẫu HUST lấy từ cấu hình sẵn có của dự án, không phải chứng nhận đúng mọi quy định của trường/khoa. NĐ30 và IEEE chưa được triển khai; đặc biệt không tự chuyển báo cáo sang hai cột.

Tự sửa phông/cỡ chữ thân bài, căn đều và khoảng cách đoạn cho các đoạn thường đủ điều kiện; đặt phông mặc định và lề/khổ giấy cho section dọc một cột; căn giữa đoạn chỉ chứa ảnh trong dòng. Giữ nguyên căn giữa/phải có sẵn, tiêu đề, mục lục, danh sách, trang ngang, section nhiều cột, bảng, trường tự động, công thức và đối tượng. Phông ký hiệu và cỡ chữ trên/dưới được bảo vệ.

Không xóa đoạn trống, không cắt khoảng trắng, không xóa hoặc thêm Tab, không tự đổi tiêu đề giả thành Heading 1. Các đoạn dùng khoảng trắng/Tab để căn lề và tiêu đề cần suy đoán được cảnh báo. Những đoạn này có thể chưa được chuẩn hóa tự động. Không tự co bảng, đổi kích thước ảnh, tạo mục lục hay viết lại nội dung.

## Bảo toàn dữ liệu

Chỉ sửa hai thành phần `word/document.xml` và `word/styles.xml`. Kiểm tra cấu trúc XML trước/sau, bỏ qua đúng các thuộc tính trình bày cho phép sửa (`jc`, `spacing`, `ind`, `widowControl`, `rFonts`, `sz`, `szCs`, `pgMar`, `pgSz`) tại đúng các thẻ thuộc tính của chúng. Mọi ký tự trong nút văn bản, kể cả khoảng trắng, Tab, trường, liên kết, revision, công thức, hình và cấu trúc bảng phải giữ nguyên. Các thành phần còn lại của ZIP được đối chiếu byte-for-byte. Nếu đối chiếu thất bại thì không xuất tệp. Chạy thử định dạng lần hai để xác nhận kết quả ổn định.

Đây là kiểm tra dữ liệu và thuộc tính trình bày. Ứng dụng không có bộ dàn trang Word, không xem trước DOCX theo trang và không đánh giá chất lượng văn bản. Điểm hiển thị là tỷ lệ các thuộc tính được kiểm tra khớp mẫu; 100% không có nghĩa toàn bộ tài liệu đã đạt chuẩn. Mở bản tải về bằng Word để xem lại ngắt trang, ảnh và bảng trước khi nộp/in. Máy mở tệp cần có phông tương ứng để hiển thị chính xác.

## API

| Phương thức | Đường dẫn | Kết quả |
| --- | --- | --- |
| GET | `/` | Giao diện web |
| GET | `/api/v1/health` | Trạng thái tiến trình |
| GET | `/api/v1/profiles` | Mẫu và thông số trình bày |
| POST | `/api/v1/lint` | Multipart `file`, `profile=hust\|report`; trả JSON HTTP 201 |
| GET | `/api/v1/sessions/{uuid}/download` | Tệp DOCX với tên `_doclint.docx` |
| DELETE | `/api/v1/sessions/{uuid}` | Xóa tệp kết quả và báo cáo; HTTP 204 |

JSON trả về có `session_id`, `expires_at`, `filename`, `download_url`, `score`, `changes`, `warnings`, `summary`, `integrity`. Không trả nội dung tài liệu trong báo cáo. Đường dẫn tải xuống chứa UUID đóng vai trò quyền truy cập; không chia sẻ nó nếu tài liệu riêng tư.

Giới hạn: 15 MiB/tệp, 80 MiB tổng giải nén, 8 MiB/mục XML, 2.000 mục ZIP. Cả upload có Content-Length và luồng chunked đều được chặn kích thước trước khi phân tích multipart. Từ chối gói trùng tên mục, đường dẫn bất thường, CRC hỏng, DTD/entity, macro, chữ ký số, tệp có mật khẩu và WordprocessingML Strict chưa hỗ trợ. Không giải nén đường dẫn ra đĩa hay tải tài nguyên từ tài liệu.

Kết quả và báo cáo được lưu tại thư mục riêng của UUID dưới `${DOCLINT_STORAGE}` (mặc định thư mục tạm hệ thống `doclint-sessions`). Tệp gốc không lưu trong kho phiên; multipart có thể dùng tệp tạm hệ thống và được đóng sau xử lý. Phiên hết hạn sau 30 phút kể từ lúc tạo kết quả; chặn tải ngay khi hết hạn, lên lịch xóa từng phiên và quét bổ sung mỗi 10 giây/khi khởi động. Có thể xóa ngay trên giao diện. Nếu máy chủ bị dừng, việc xóa vật lý chỉ tiếp tục khi ứng dụng chạy lại; bản sao lưu/snapshot cần chính sách lưu giữ riêng của hạ tầng. Tệp được ghi vào thư mục phiên mode 0700, phản hồi có `Cache-Control: no-store`.

Triển khai công khai cần HTTPS, giới hạn request/concurrency tại reverse proxy và chính sách dọn dữ liệu ở hạ tầng. Ứng dụng hiện giới hạn 2 luồng xử lý tài liệu trên mỗi tiến trình; không cung cấp đăng nhập, quota hay mô hình multi-tenant. Không bật access log ở ví dụ khởi động để tránh ghi UUID tải xuống.

## Kiểm thử

Từ `DocLint/`, sau khi cài phụ thuộc phát triển:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Bao gồm sửa định dạng thực, lặp lại không đổi thêm, ký tự/whitespace/Tab, đoạn rỗng chứa bookmark, bảng lồng và ô gộp, OMML, ảnh, section nhiều cột/ngang, ký hiệu, heading, tệp hỏng, hạn mức, API upload/download/delete, phiên độc lập và TTL thật.

Kiểm thử trình duyệt khi server đang chạy (Chromium sẵn có):

```bash
DOCLINT_BROWSER_PATH=/usr/bin/chromium python tests/browser_smoke.py
```

Nếu chưa có Chromium, cài bằng `python -m playwright install chromium` rồi bỏ biến `DOCLINT_BROWSER_PATH`. Có thể truyền `DOCLINT_TEST_DOCX=/đường/dẫn/tệp.docx` để thử tài liệu riêng; tệp đó không được đưa vào repository. Dùng `DOCLINT_SCREENSHOT_DIR` để lưu ảnh kiểm tra ngoài repository.

## CLI

Dùng cùng lõi xử lý như web, phải chỉ định đầu ra khác tệp gốc:

```bash
python main.py input.docx output.docx --profile hust
```

`run_system_test(input_path, profile_path, output_path)` được giữ cho lời gọi cũ với mẫu HUST. Lỗi được báo ra ngoài thay vì in thông báo rồi trả thành công.

## Cấu trúc

- `api.py`: web/API, giới hạn tải lên, deadline và vòng đời phiên.
- `core/processor.py`: kiểm tra gói DOCX, xử lý, đối chiếu, báo cáo.
- `core/autofix.py`: chỉ chỉnh thuộc tính định dạng; không sửa nút nội dung.
- `core/xmlutils.py`: thứ tự phần tử OpenXML và chữ ký toàn vẹn.
- `core/profiles.py`: mẫu HUST và mẫu báo cáo phổ thông.
- `core/sessions.py`: kết quả tạm, thời hạn, xóa phiên.
- `static/`: HTML/CSS/JS, không phụ thuộc CDN.
- `tests/`: kiểm thử lõi/API và smoke test trình duyệt.

Các rule phân tích cũ trong `core/*_rule.py` còn được giữ để tương thích; báo cáo của web được tạo bởi `processor.py`, nơi phân biệt sửa tự động và cảnh báo.
