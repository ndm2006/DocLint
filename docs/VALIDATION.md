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
