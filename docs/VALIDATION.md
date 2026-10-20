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
