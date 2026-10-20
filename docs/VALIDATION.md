# Ghi nhận kiểm tra V1

Kiểm tra ngày 2026-10-19, trên Linux. Các lệnh tái lập nằm trong README.

| Phạm vi | Kết quả |
| --- | --- |
| Python 3.12.14 | 62 bài unittest qua, không bỏ qua bài tích hợp LibreOffice |
| Python 3.14.5 | Cùng 62 bài qua, không bỏ qua bài tích hợp LibreOffice |
| Tài liệu tổng hợp | 30 biến thể trong bài corpus: strict/layout, bảng, ảnh, OMML, bookmark, revision, section ngang |
| Trình duyệt Chromium | Desktop/mobile; duyệt cấu trúc; hai mẫu; ảnh trang thật; tải Word/JSON; mở lại phiên; đổi phương án từ bản gốc; xóa phiên; không có lỗi JavaScript |
| CLI | Phân tích và dàn mẫu thành 6 trang; mục lục khớp PDF; chặn ghi đè tệp gốc |
| Báo cáo người dùng đã cung cấp | Xử lý thành 7 trang, cổng toàn vẹn qua, mục lục khớp PDF; không đưa tài liệu hoặc kết quả riêng vào Git |
| Container | Build thành công; luồng HTTP đầy đủ qua khi runtime không có mạng, user không phải root, filesystem chỉ đọc, tmpfs và giới hạn tài nguyên |
| Kiểm tra tĩnh | Ruff F/E9, cú pháp JavaScript, pip check và cấu hình Compose qua |

Nhóm kiểm thử có trường hợp footer chứa ảnh/liên kết, field lồng nhau, quan hệ thiếu và header trang đầu vốn ẩn. Không thay footer một phần rồi báo số trang đã hoàn tất.

Chưa chạy ứng dụng trực tiếp trên Windows hoặc Microsoft Word. Tệp khởi động `.cmd` đã được rà soát; kiểm tra Python 3.14.5 ở trên thực hiện trên Linux. Bộ dựng PDF không chứng minh Word sẽ ngắt trang giống hệt. Cần nghiệm thu trực tiếp trên Windows/Word với phông người dùng và kiểm thử khả dụng để đánh giá mức độ hài lòng.

## Bản sửa lỗi tải lên, 2026-10-20

- File người dùng gửi để báo lỗi đọc được 13 khối, dựng PDF gốc 1 trang và đi đến màn hình duyệt trên Linux. Luồng trình duyệt desktop/mobile với chính tệp này cũng qua, gồm dàn trang, xem trước, tải Word/JSON, đổi mẫu, mở lại phiên và xóa. Không đưa tệp riêng vào Git.
- 67 bài unittest qua trên cả Python 3.12.14 và 3.14.5. Các bài mới kiểm tra lỗi hệ điều hành ở bộ dựng không chặn Word, lỗi đọc cấu trúc vẫn chặn xuất, thông tin chẩn đoán không chứa thông báo ngoại lệ/nội dung/tên tệp và quyền truy cập hết khi xóa phiên.
- Smoke test trình duyệt riêng chủ động gây lỗi quyền truy cập cho bộ xem trước: vẫn duyệt được, tải chẩn đoán JSON được, tải Word sau kiểm chứng được, tải lại trang và xóa phiên được; không có lỗi JavaScript. Lệnh tái lập: `DOCLINT_BROWSER_PATH=/usr/bin/chromium python tests/browser_support_smoke.py` từ thư mục `DocLint/`.
- Nhận diện `soffice.com` và môi trường AppData riêng trên Windows được kiểm tra bằng mô phỏng. Đây chưa phải kiểm tra chạy thực trên Windows. Chưa xác định được ngoại lệ gốc trên máy người dùng; bản sửa cung cấp mã và gói chẩn đoán để xác định nếu sự cố còn xảy ra.
- Image sau sửa build thành công và qua lại smoke test HTTP trong container không mạng, filesystem chỉ đọc và user không phải root.

## Duyệt theo nhóm và tách trang bìa/mục lục, 2026-10-20

- Nhật ký người dùng ghi `OSError` trong `render_pdf`, tại context thư mục tạm; nội dung đã qua cổng toàn vẹn. Log cũ không có errno/winerror nên chưa phân biệt được tạo hay dọn thư mục. Bản mới phân biệt hai bước, ghi mã số hệ điều hành an toàn và không biến lỗi dọn dẹp thành lỗi của một PDF đã kiểm tra thành công. Workspace còn khóa vẫn thuộc phiên riêng và được janitor thử dọn lại khi job không còn chạy.
- 85 unittest qua trên Python 3.12.14 và 3.14.5, không bỏ qua bài tích hợp Office. Bổ sung tình huống bìa ít dòng, báo cáo bắt đầu ngay bằng chương, phần mở đầu trước Heading, ngắt trang sẵn có, intro khóa nguyên cấu trúc, ID paragraph của Word có/không có tham chiếu và lỗi dọn thư mục không che lỗi gốc.
- Tệp DOCX đã gửi và có SHA khớp nhật ký được dựng thành **3 trang**: bìa, mục lục, nội dung. Số trang mục lục khớp PDF; phần mở đầu không còn bị đưa vào bìa. Tài liệu và bản dựng riêng không nằm trong Git.
- UI của tệp đó có **2 nhóm** cần xem lại thay vì lựa chọn trên 13 đoạn. Báo cáo mẫu có 9 đề mục được nhận theo chuỗi nhất quán và 1 nhóm xác nhận hàng tiêu đề bảng. Case 20 đề mục đánh số đơn chưa rõ được gộp thành một câu hỏi, mặc định giữ nguyên.
- Smoke trình duyệt qua với tệp người dùng và báo cáo mẫu: desktop/mobile, nhóm lựa chọn, menu nâng cao đóng mặc định, chỉ tìm vùng khóa theo từ khóa, hai mẫu, preview thật, tải Word/JSON, đổi phương án, nối lại phiên và xóa; không có lỗi JavaScript. Luồng preview bị lỗi vẫn tải chẩn đoán và Word đã kiểm chứng được.
- Các kiểm tra chạy trên Linux; hành vi khóa thư mục Windows được mô phỏng. Vẫn cần chạy lại trên Windows/Word thực để xác nhận môi trường người dùng và phân trang theo phông cài tại máy.
