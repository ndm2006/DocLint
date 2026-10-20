# DocLint V1

**Hoàn thiện báo cáo Word bằng bộ quy tắc, không dùng API AI trả phí.**

Tải DOCX → xác nhận các nhóm còn chưa chắc chắn → dàn trang theo vai trò → đối chiếu nội dung → xem từng trang trước/sau → tải Word, PDF và nhật ký. Phạm vi V1 là báo cáo học thuật một cột, không phải mọi kiểu tài liệu Word.

## Bắt đầu trên Windows

Bạn đã có Python thì giữ bản đang dùng. Cần Python 3.12–3.14 và **LibreOffice** để có đầy đủ bản dựng, mục lục và kiểm tra trang. LibreOffice miễn phí: [trang tải chính thức](https://www.libreoffice.org/download/download-libreoffice/).

1. Tải ZIP nhánh `codex/doclint-web`, giải nén vào một thư mục mới để giữ code cũ.
2. Cài LibreOffice nếu máy chưa có. Không cần mua Microsoft Office để chạy máy chủ.
3. Dừng Terminal DocLint cũ bằng `Ctrl+C` nếu đang dùng cổng 8000.
4. Mở thư mục có README này, bấm đúp **`RUN_DOCLINT.cmd`**.
5. Lần đầu script tạo môi trường riêng và cài thư viện; sau đó tự mở trình duyệt. Giữ cửa sổ chạy mở trong lúc sử dụng.

Nếu chưa cài LibreOffice, web vẫn hoạt động và báo kết quả **chưa hoàn tất** cho những bước cần dựng PDF; không giả lập bản xem trước. Nếu cài Office ở vị trí riêng, đặt biến `DOCLINT_SOFFICE` là đường dẫn đầy đủ đến `soffice.exe` rồi chạy lại.

Trên Windows, nếu có `soffice.com` cạnh `soffice.exe`, DocLint ưu tiên bộ gọi console để chờ quá trình chuyển PDF kết thúc. Bộ dựng có thư mục cấu hình và AppData tạm riêng. Tệp khởi động cũng tự bổ sung `pip` bằng `ensurepip` nếu môi trường ảo còn thiếu.

Nếu web báo lỗi ngay sau khi tải lên: bản mới giữ màn hình duyệt khi cấu trúc Word đã đọc được nhưng bộ xem trước gặp lỗi. Khi xuất hiện nút **Tải thông tin lỗi để hỗ trợ**, tải JSON và gửi cùng mô tả bước lỗi. JSON chứa mã tham chiếu, giai đoạn, loại lỗi, mã hệ điều hành nếu có, vị trí code và phiên bản môi trường; không chứa nội dung, tên tài liệu, đường dẫn máy cá nhân hoặc thông báo ngoại lệ thô. Chỉ tải được trong thời hạn phiên. Lỗi cấu trúc thực sự vẫn chặn xuất Word. Khi dùng bản code mới, hãy dừng Terminal cũ trước khi khởi động lại; launcher sẽ không tự mở một bản build cũ đang chiếm cổng.

Chạy thủ công trong PowerShell, tại thư mục có README:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\DocLint\requirements.txt
.\.venv\Scripts\python.exe .\DocLint\launch.py
```

Mở trình duyệt trên chính máy chạy ứng dụng, nhập `http://127.0.0.1:8000`. Cổng khác có thể đặt qua `DOCLINT_PORT` khi dùng launcher. Launcher không dừng hay ghi đè một dịch vụ đang chạy trên cổng đó.

## Cách thử để thấy khác biệt

Trong giao diện có **Tải báo cáo mẫu có lỗi bố cục**. Đây là tài liệu tổng hợp, không chứa thông tin thật của người dùng. Có thể tạo lại bằng `python DocLint/examples/create_demo.py /đường/dẫn/mới.docx`.

Bản đối chiếu `case_00` với bìa tối giản đã căn giữa: [Word](DocLint/examples/case_00_bia_toi_gian_da_sua.docx) · [PDF](DocLint/examples/case_00_bia_toi_gian_da_sua.pdf). Đây là mẫu tổng hợp trong bộ kiểm thử; phần trang ngang được giữ.

Sau khi tải lên:

- Hệ thống giữ Heading sẵn có và xét cây đề mục theo từng chương/phần/bài. Ví dụ: `BÀI TẬP 1` là cấp 1, `1. Giới thiệu` bên trong là cấp 2, các tiểu mục `a), b)` có nội dung riêng là cấp 3; số mục được bắt đầu lại ở bài tiếp theo. Chuỗi La Mã được phân biệt với chữ cái A, B, C, D; danh sách ngắn liên tiếp vẫn cần duyệt. Nhóm còn phân vân có ba lựa chọn riêng: **Giữ nguyên định dạng** (mặc định), **Chuẩn hóa thành văn bản thường**, hoặc **Dùng làm đề mục**. Lựa chọn giữ nguyên được đối chiếu XML chính xác, gồm phông, cỡ chữ, căn lề và cấu trúc.
- Chọn HUST hoặc báo cáo phổ thông. Mẫu HUST xuất phát từ cấu hình của dự án, chưa phải chứng nhận đúng mọi quy định trường/khoa.
- Giữ bìa hoặc chọn mẫu học thuật/tối giản để dàn phần thông tin bìa hiện có thành trang riêng. Cả hai mẫu căn giữa các dòng văn bản an toàn và bảng bìa, bỏ thụt lề sót ở logo; chế độ layout làm sạch Space/Tab đầu và cuối từng dòng bìa nhưng giữ khoảng cách bên trong. Bảng thành viên dùng khoảng cách ô gọn hơn. Bộ nhận diện hỗ trợ nhãn tiếng Việt/Anh, ưu tiên ngắt trang/section có sẵn và phân biệt Heading dùng trang trí bìa với đề mục thân bài. Chương và phần mở đầu vẫn nằm ngoài bìa.
- Căn bằng Space/Tab chỉ được hỏi theo nhóm khi ý đồ chưa rõ. Chế độ giữ nguyên ký tự, phạm vi bảng/ảnh, số trang và tìm vùng khóa nằm trong **Tùy chọn nâng cao**; không liệt kê tất cả đoạn để bạn chọn.
- Chỉ hỏi xác nhận hàng đầu cho nhóm bảng có dấu hiệu giống tiêu đề cột. Bảng đã có hàng tiêu đề hoặc chú thích chỉ có một đối tượng phù hợp không cần chọn lại.
- Mục lục chỉ có hai lựa chọn phù hợp với tài liệu: giữ hiện tại hoặc tạo/thay thế. Mục lục bắt đầu trên trang riêng và nội dung bắt đầu ở trang sau mục lục; mục lục dài được phép tiếp tục sang nhiều trang.
- Xem trước–sau, đọc cảnh báo, tải bản Word riêng và mở Word xem lần cuối.

Giao diện mặc định dàn bìa học thuật khi nhận diện được bìa, tạo/thay mục lục khi có đủ tiêu đề và dùng số trang học thuật. Phần đầu dùng La Mã, Chương 1 bắt đầu từ 1 khi xác định được cấu trúc. Tham khảo/phụ lục mặc định được đồng bộ định dạng, luôn giữ nội dung; tùy chọn nâng cao cho phép giữ cả cách trình bày cũ.

Caption có thể chuyển sang SEQ/REF mà giữ nhãn hiện tại; danh mục hình/bảng và viết tắt lấy từ thông tin sẵn có. Danh sách Word thật và việc chuyển khối chữ ký về cuối thân bài là tùy chọn nâng cao. Chi tiết theo bảy mức ưu tiên và giới hạn: [Đối chiếu đánh giá bố cục](docs/PRIORITY_LAYOUT_REVIEW.md).

Mỗi lần đổi phương án đều xử lý từ **bản gốc**, tránh tích lũy những thay đổi không mong muốn.

Tài liệu có khung chữ đặt theo tọa độ được xử lý chọn lọc: giữ nguyên vùng khung cùng các đoạn chia sẻ vùng đó; chỉ chỉnh phần văn bản độc lập bên ngoài. Ranh giới được xác định từ ngắt trang/ngắt section thật. Khi chưa tách được an toàn, giữ cả vùng rộng hơn. Lề/khổ giấy dùng chung và các thao tác có thể xê dịch vùng được giữ (dựng bìa, mục lục, số trang, danh mục, chuyển chữ ký) được bảo vệ. Nhãn trong hình gắn với một đoạn được giữ cùng đối tượng, vẫn cho phép xử lý thân bài độc lập. Xem [cơ chế bảo vệ bố cục](docs/SELECTIVE_LAYOUT.md).

Nếu toàn tài liệu được dựng bằng các cụm đối tượng, tệp tải về giữ nguyên từng byte của tệp gốc, giao diện ghi **Đã giữ nguyên tài liệu**, trạng thái `partial`; không coi là đã chuẩn hóa. Hãy thử lại từ bản gốc nếu bản xuất cũ đã bị lệch.

## Đã triển khai và phạm vi an toàn

| Nhóm | Hành vi V1 |
| --- | --- |
| Phân tích | Mã khối, style kế thừa, vai trò, section, vùng bìa, mục lục, tham khảo/phụ lục; nhận định có giải thích |
| Tiêu đề | Tự nhận chuỗi đề mục rõ ràng; nhóm chưa chắc chỉ hỏi giữ nguyên hoặc dùng cấp đề xuất; tạo Heading/outline thật, không đổi tên hoặc đánh lại số |
| Thân bài | Phông/cỡ theo vai trò, khoảng cách, giãn dòng, căn lề; giữ nhấn mạnh, chỉ số và phông ký hiệu |
| Space/Tab | Có chế độ giữ nguyên ký tự; làm sạch đầu đoạn có điều kiện hoặc theo lựa chọn cụ thể; không cắt ký tự giữa nội dung |
| Enter | Làm sạch chuỗi rỗng trước chương và khoảng đệm bìa/mục lục theo phạm vi; bảo vệ bookmark, ngắt section, đối tượng, revision và tham chiếu paragraph ID |
| Danh sách | Giữ số/ký hiệu đang có, chuẩn hóa hình thức; giữ style cung cấp numbering; tùy chọn chuyển chuỗi số gõ tay rõ ràng sang numbering thật |
| Bảng có lưới rõ | Độ rộng theo vùng in, phân bổ cột, đệm ô, kiểu chữ/viền, hàng tiêu đề có xác nhận; hỗ trợ ô gộp khi lưới đầy đủ, không đổi ô/số liệu |
| Ảnh | Thu ảnh vừa vùng in; phóng ảnh độ phân giải cao đang quá nhỏ với giới hạn chiều cao/mật độ điểm ảnh; giữ dữ liệu và tỷ lệ |
| Chú thích | Liên kết đối tượng liền kề duy nhất hoặc được duyệt; giữ ảnh/chú thích cùng nhau; SEQ/REF khi đủ căn cứ, không đánh lại nhãn mơ hồ |
| Bìa | Mẫu học thuật/tối giản từ thông tin sẵn có, tách thành trang riêng; nhận diện ranh giới trước phần mở đầu, không bịa tên/ngày/logo |
| Mục lục | Trường TOC thật trong phạm vi thân bài, bắt đầu trang riêng và tách phần nội dung; thay mục lục cũ chỉ khi được duyệt, đối chiếu tối đa 3 bản dựng |
| Số trang | Footer riêng, bảo toàn phần gốc; liên tục hoặc học thuật: bìa riêng, phần đầu La Mã, thân bài từ 1, phụ lục tiếp tục; section phức tạp được giữ và báo rõ |
| Xem trước | PDF cục bộ, ảnh từng trang, điều hướng và đánh dấu các trang định vị được thay đổi/cảnh báo |
| Toàn vẹn | Đối chiếu trước và sau đóng gói; vùng khóa kiểm tra chính xác; thành phần không sửa giữ byte-for-byte |
| Vận hành | Hàng đợi giới hạn, timeout, hủy, TTL từ lúc tiếp nhận, khôi phục trạng thái sau gián đoạn |

Các tình huống như bảng lồng/lưới không đầy đủ, ảnh nổi, nhóm nhiều ảnh, content control, công thức, revision và bố cục ngang/nhiều cột được bảo vệ hoặc cảnh báo tùy phạm vi, không ép sửa.

Đặc tả đối chiếu từng lỗi và tiêu chí: [docs/V1_SCOPE.md](docs/V1_SCOPE.md).

## Quy tắc bảo toàn nội dung

`v1/package.py` giữ một bản cấu trúc kỳ vọng độc lập với định dạng. Chỉ các thao tác nội dung có phạm vi cụ thể được đăng ký mới được phép: làm sạch đầu đoạn đã cho phép, bỏ đoạn thật sự rỗng đủ điều kiện, thay vùng mục lục đã duyệt, thêm cấu trúc sinh tự động, chuyển caption/tham chiếu sang field mà giữ chữ, chuyển tiền tố danh sách sang numbering theo tùy chọn, chuyển khối chữ ký rõ ràng theo yêu cầu và đổi ngắt trang thành ngắt section. Thay câu chữ, số, công thức, đối tượng, liên kết hoặc dữ liệu bảng ngoài phạm vi đó sẽ làm đối chiếu thất bại và **không xuất kết quả**.

Các style mới được tách khỏi style gốc, tránh ảnh hưởng vùng khóa. Vùng khóa còn được so sánh chính xác thuộc tính/cấu trúc; section dùng chung có thể được giữ lề/khổ giấy để bảo vệ vùng khóa. Tệp gốc luôn tồn tại riêng trong thời hạn phiên.

Không coi việc bỏ mọi khoảng trắng rồi so sánh là kiểm chứng nội dung. Chế độ làm sạch giữ khoảng trắng giữa chữ và Tab giữa nội dung; mọi chỉnh sửa ký tự hợp lệ có nhật ký.

## Bản dựng, phông chữ và trạng thái kết quả

LibreOffice chỉ tạo PDF; DOCX do LibreOffice ghi lại không được dùng làm kết quả. PDFium đọc trang và tạo PNG. Dựng lại hữu hạn để khớp số trang mục lục; không lặp AI, không tự thu chữ để bớt trang.

- `review`: đã phân tích, chờ duyệt hoặc cần thay đổi lựa chọn.
- `ready`: các bước xử lý yêu cầu đã chạy và nội dung được đối chiếu; vẫn có thể có cảnh báo cần xem lại.
- `partial`: nội dung đã đối chiếu nhưng bản dựng/mục lục/số trang chưa hoàn tất; tải Word được và cảnh báo rõ phần chưa kiểm tra.
- `failed`: không hoàn tất phân tích; chưa có kết quả để tải.

Mục lục dùng bookmark phạm vi thân bài, tránh đưa tiêu đề bìa vào khi cập nhật field. Trong chế độ layout, khoảng đệm rỗng ở ranh giới bìa/mục lục được làm sạch có kiểm soát. Paragraph ID và dấu phiên chỉnh sửa của Word không ngăn việc xóa đoạn thật sự rỗng nếu không có tham chiếu ngoài; bookmark, revision và mã được tham chiếu vẫn được bảo vệ.

Khi số trang mục lục đã được đối chiếu, DOCX lưu các số đó và đánh dấu mục lục đã cập nhật. Tệp có mục lục do DocLint tạo không ép Word cập nhật toàn bộ field khi vừa mở, tránh mất kết quả trước khi Word phân trang xong. Mục lục vẫn là trường TOC có thể cập nhật: sau khi chỉnh sửa nội dung hoặc đổi phông trong Word, bấm chuột phải vào mục lục → **Update Field / Cập nhật trường**. Nếu chưa dựng được PDF, mục lục vẫn có dấu chờ và cảnh báo chưa xác minh, không được đánh dấu hoàn tất.

Máy chủ phải có phông phù hợp. Linux có thể dùng Liberation Serif thay Times New Roman hoặc Carlito thay Calibri; khi phát hiện thay phông, giao diện thông báo. LibreOffice và Word có thể ngắt dòng/trang khác nhau. Bản xem trước không phải cam kết giống Word từng điểm ảnh.

Kiểm tra theo trang có phạm vi: trang ít chữ, tiêu đề gần cuối trang, chữ/ảnh ngoài khổ/vùng in định vị được. Liên kết trang thay đổi chỉ dựa trên khớp văn bản đủ rõ; không suy đoán mọi vị trí bảng/ảnh. 100% thuộc tính khớp mẫu không được dùng làm điểm đạt chuẩn toàn tài liệu.

Nếu Windows chưa dọn được thư mục tạm sau chuyển PDF, lỗi dọn dẹp không làm mất một PDF đã kiểm tra thành công. Thư mục vẫn nằm trong phiên riêng và được thử dọn lại khi job không còn chạy. Lỗi tạo thư mục tạm có mã chẩn đoán riêng; không được báo thành đã dựng PDF.

## Chạy trên Linux/cloud

Từ thư mục gốc:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r DocLint/requirements-dev.txt
cd DocLint
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m uvicorn api:app --host 0.0.0.0 --port 8000 --no-access-log
```

Cài LibreOffice và phông bằng trình quản lý gói của máy chạy. Môi trường cloud đã chuẩn bị dùng `/workspace/.venvs/doclint/bin/python` và `soffice` có sẵn. Mỗi tác vụ cloud đã cô lập; dùng checkout hiện có, không tạo worktree nếu không được yêu cầu.

## API V1

| Phương thức | Đường dẫn | Hành vi |
| --- | --- | --- |
| GET | `/api/v1/health` | Health cơ bản |
| GET | `/api/v1/capabilities` | Phiên bản, bộ dựng, giới hạn, không dùng AI |
| GET | `/api/v1/profiles` | Mẫu và thông số |
| POST | `/api/v1/jobs` | Multipart `file`; HTTP 202, trả URL theo dõi |
| GET | `/api/v1/jobs/{id}` | Trạng thái, phân tích, lựa chọn và báo cáo riêng của phiên |
| POST | `/api/v1/jobs/{id}/format` | JSON lựa chọn; HTTP 202; luôn bắt đầu từ bản gốc |
| GET | `/api/v1/jobs/{id}/download` | Word sau kiểm chứng |
| GET | `/api/v1/jobs/{id}/report` | JSON nhật ký và kết quả kiểm tra |
| GET | `/api/v1/jobs/{id}/diagnostic` | Thông tin kỹ thuật an toàn khi gặp lỗi; dùng được cả khi chưa có kết quả |
| GET | `/api/v1/jobs/{id}/preview/{original\|result}.pdf` | PDF tương ứng |
| GET | `/api/v1/jobs/{id}/pages/{original\|result}/{n}.png` | Ảnh trang theo nhu cầu |
| DELETE | `/api/v1/jobs/{id}` | Hủy và xóa; 204 khi xong, 202 nếu đang dừng |

Các trường chọn định dạng được kiểm tra bởi `v1/options.py`: `profile`, `mode`, `heading_levels`, `preserved_candidates`, `locked_blocks`, `preserve_cover`, `preserve_references`, `preserve_appendices`, `cover`, `cover_end`, `table_headers`, `caption_links`, `layout_decisions`, `toc`, `page_numbers`, `hide_first_page_number`, `normalize_tables`, `normalize_images`. Trường không biết bị từ chối. UUID trong URL là quyền truy cập phiên; không chia sẻ URL tài liệu riêng tư.

Endpoint `/api/v1/lint` và `/api/v1/sessions/...` cũ được giữ để tương thích luồng định dạng cơ bản trước V1. Giao diện V1 dùng Jobs API để phân tích/duyệt/xem trước, không dùng endpoint cũ.

## Giới hạn và dữ liệu tạm

- 15 MiB tải lên; 80 MiB giải nén; 8 MiB/mục XML; 2.000 mục ZIP; 5.000 khối trực tiếp.
- Xem trước tối đa 120 trang; tối đa 60 giây cho mỗi lần gọi Office, tối đa 3 lượt dựng để đối chiếu mục lục.
- Dựng ảnh tối đa 40 triệu điểm ảnh/mỗi ảnh, 80 triệu điểm ảnh/tệp để giới hạn bộ nhớ.
- Một worker cho luồng Jobs, tối đa 4 việc chờ; 10 lượt tải lên/phút theo IP trực tiếp và tối đa 10 lần dàn trang/phiên.
- Bản gốc, phân tích, PDF, PNG và kết quả nằm trong thư mục UUID mode 0700, hết hạn sau 30 phút từ lúc tiếp nhận; đọc/tải/xử lý lại không gia hạn.
- Hủy khi đang chạy phải dừng tiến trình trước khi xác nhận đã xóa. Có deadline, quét bổ sung mỗi 10 giây và dọn/khôi phục khi khởi động.
- Khi máy dừng, việc xóa vật lý chỉ tiếp tục khi dịch vụ chạy lại. Không đưa kho phiên vào snapshot/backup; không cam kết xóa pháp chứng trên đĩa/hạ tầng ngoài ứng dụng.

`DOCLINT_STORAGE` chọn kho tạm; Jobs nằm ở thư mục con `v1-jobs`. Không ghi nội dung tài liệu hoặc raw log Office ra log máy chủ. Phản hồi riêng tư có `Cache-Control: no-store`; giao diện chỉ giữ UUID trong sessionStorage để nối lại sau khi tải lại trang.

## Đóng gói container

```bash
docker compose up --build
```

Compose chạy user không phải root, filesystem chỉ đọc, dữ liệu tạm trên tmpfs, bỏ capabilities, giới hạn RAM/CPU/PID và mạng runtime `internal`. Cổng chỉ gắn vào loopback máy chủ. Không mount thư mục chứa bí mật hoặc bật Internet cho bộ dựng. Tệp nhúng/ActiveX, trường nạp tài nguyên ngoài và SVG chủ động không được chuyển cho Office; liên kết ngoài bị vô hiệu hóa trong bản dựng tạm, không sửa liên kết gốc trong DOCX.

Public deployment vẫn cần HTTPS, giới hạn lưu lượng tại reverse proxy và đánh giá bảo mật/hạ tầng. Tự chạy Python trực tiếp không cung cấp cùng mức cô lập hệ điều hành như container.

Nếu mạng build có TLS proxy doanh nghiệp, Dockerfile hỗ trợ BuildKit secret `build_ca` là **bundle CA công khai được tổ chức tin cậy**. Chỉ truyền CA hợp lệ khi cần; không truyền khóa riêng, không tắt TLS và không bỏ kiểm tra chữ ký gói. Bundle chỉ mount lúc build, không giữ trong image. Cấu hình proxy/DNS thuộc máy build; không hardcode vào repository.

Không có phí API AI; máy chủ, CPU dựng PDF và băng thông vẫn có chi phí.

## Kiểm thử

Từ thư mục `DocLint/`, sau khi cài `requirements-dev.txt`:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
python -m ruff check v1 api.py main.py launch.py tests/test_v1_engine.py tests/test_v1_jobs.py tests/v1_fixtures.py examples --select F,E9
```

Có kiểm thử nội dung/whitespace, Heading và style kế thừa, list numbering, khóa vùng, bảng gộp/lồng, OMML, ảnh, revision, cache mục lục, footer, timeout, hàng đợi, request đồng thời, giới hạn và TTL. Nhóm corpus tạo 30 tài liệu tổng hợp khác nhau trong bộ nhớ; không đưa báo cáo riêng của người dùng vào Git. Bài tích hợp Office được đánh dấu bỏ qua khi không có LibreOffice, không được tính là đã xác minh bản dựng.

Smoke test trình duyệt khi server đang chạy:

```bash
DOCLINT_BROWSER_PATH=/usr/bin/chromium python tests/browser_smoke.py
```

Có thể đặt `DOCLINT_TEST_URL`, `DOCLINT_TEST_DOCX`, `DOCLINT_SCREENSHOT_DIR`. Nếu dùng Chromium của Playwright, cài `python -m playwright install chromium` và bỏ biến đường dẫn browser. Người dùng thông thường không cần Node.js hay Playwright để chạy web.

## CLI

```bash
python main.py input.docx --analyze > analysis.json
python main.py input.docx output.docx --profile hust --preview-dir /thư/mục/riêng
python main.py input.docx output.docx --options doclint-report.json
```

Có thể dùng lại `options` từ nhật ký của chính tệp gốc; SHA-256 được kiểm tra khi đọc nhật ký để tránh áp lựa chọn vào nhầm tài liệu. Không tự duyệt đề mục còn phân vân khi chạy CLI. Đầu ra phải khác tệp gốc. `run_system_test(input, profile_path, output)` còn được giữ cho mẫu HUST, dùng pipeline V1 và báo lỗi ra ngoài.

## Mã nguồn chính

- `v1/analysis.py`: bản đồ khối, style kế thừa, phân loại và đề xuất.
- `v1/editor.py`, `design.py`: các quy tắc và mẫu theo vai trò.
- `v1/package.py`: gói OPC, phép sửa được phép, kiểm chứng và vùng khóa.
- `v1/fields.py`: TOC và footer/số trang được chấp thuận.
- `v1/renderer.py`, `pipeline.py`: PDF/PNG, kiểm tra trang và đối chiếu cuối.
- `v1/jobs.py`, `routes.py`: hàng đợi, quyền truy cập phiên và vòng đời.
- `static/`: giao diện không phụ thuộc CDN.
- `core/`: tiện ích OpenXML và engine/endpoint tương thích cũ.

Giấy phép phụ thuộc: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Không mặc định coi “miễn phí tải thư viện” là được bỏ nghĩa vụ giấy phép khi phân phối.
