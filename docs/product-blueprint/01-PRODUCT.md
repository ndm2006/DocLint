# 01 — Định hướng sản phẩm và phạm vi

**Trạng thái: dự thảo 0.1.** Các quyết định dưới đây là đề xuất để nhóm chốt; các chức năng mới không được mô tả như đã có mã.

## 1. Vấn đề cần giải quyết

Người dùng đã có nội dung báo cáo, thường là bản nháp từ AI, nội dung sao chép hoặc phần đóng góp của nhiều thành viên. Các phần có phông, khoảng cách, đề mục và cách căn chỉnh khác nhau. Việc sửa từng đoạn tốn thời gian, có thể làm phần khác xê dịch và khó biết đã sửa những gì.

**Công việc người dùng muốn hoàn thành:** “Khi đã có nội dung, tôi muốn nhanh chóng có một bản báo cáo trình bày thống nhất để kiểm tra và nộp, mà không phải căn chỉnh từng đoạn hoặc lo hệ thống viết lại ý của mình.”

V1 tập trung vào sinh viên, nhóm đồ án và người làm báo cáo học thuật tiếng Việt một cột. Việc dùng nội dung từ AI không làm thay đổi trách nhiệm của tác giả đối với tính đúng đắn và nguồn trích dẫn.

## 2. Mục tiêu cốt lõi

**Kết quả chính:** bản DOCX đầu ra nhất quán hơn theo mẫu được chọn, đồng thời người dùng hiểu được phạm vi thay đổi và phần còn cần kiểm tra.

Giá trị dự kiến gồm:

- Giảm thao tác định dạng lặp lại.
- Giảm số quyết định người dùng phải thực hiện.
- Cải thiện tính nhất quán theo vai trò, không chỉ thay phông toàn bộ tệp.
- Bảo vệ nội dung và vùng cấu trúc không đủ điều kiện chỉnh sửa.
- Cung cấp bằng chứng và giải thích về kết quả.

“Wow” được đánh giá bằng kết quả hữu ích và ít công kiểm tra lại, không bằng số lượng thay đổi, số tính năng hoặc một điểm đẹp không có căn cứ.

## 3. Các ràng buộc không được đánh đổi

| Mã | Ràng buộc |
|---|---|
| INV-01 | Không viết lại câu, thêm kiến thức, dịch, tóm tắt hoặc sửa số liệu chuyên môn. |
| INV-02 | Mọi thay đổi ký tự phải thuộc một phép dọn bố cục hẹp đã được cho phép; chế độ strict không thay ký tự nguồn. |
| INV-03 | Vùng được giữ nguyên phải được bảo vệ cả thuộc tính trực tiếp và ảnh hưởng từ kiểu/section/quan hệ dùng chung. |
| INV-04 | Kiểm tra toàn vẹn thất bại thì không cung cấp ứng viên đó như một kết quả đã chuẩn hóa hợp lệ. |
| INV-05 | Mỗi lần chạy lại dùng bản gốc của phiên, không sửa chồng lên kết quả trước. |
| INV-06 | Nhật ký phân biệt phát hiện, đề xuất, đã áp dụng, bỏ qua và thất bại; không ghi dự định như hành động đã hoàn thành. |
| INV-07 | Đúng PDF không đồng nghĩa đã kiểm chứng đúng Microsoft Word; trạng thái phải thể hiện phạm vi bằng chứng. |
| INV-08 | Nội dung DOCX là dữ liệu, không phải lệnh có quyền sửa cấu hình, chạy mã hoặc thay chính sách hệ thống. |

Không chuyển gạch đầu dòng thành đoạn văn diễn giải, tự thêm giải thích cho hình hoặc tự tạo nguồn tham khảo. Các việc này thay đổi nội dung; hệ thống có thể cảnh báo nếu phát hiện vấn đề nhưng không tự viết thay.

## 4. Phạm vi đầu vào và đầu ra

### Phạm vi chính V1

- Đầu vào: DOCX có văn bản theo luồng, ưu tiên báo cáo một cột.
- Thành phần hỗ trợ có điều kiện: thân bài, đề mục, danh sách, bìa có sẵn, bảng đơn giản, ảnh inline, chú thích và mục lục.
- Ngoại lệ: trang ngang, phần nhiều cột, khung đoạn, hộp chữ, ảnh nổi, bảng lồng và cấu trúc phức tạp được phân tích để giữ/bỏ qua phù hợp.
- Đầu ra: DOCX vượt cổng kiểm tra; PDF/ảnh trang khi dựng được; báo cáo thay đổi và cảnh báo.
- Nếu toàn tệp không có vùng sửa an toàn: bảo tồn bản gốc, giải thích rõ, không báo đã chuẩn hóa toàn bộ.

### Chưa thuộc cam kết V1

- Tạo báo cáo từ một chủ đề, viết lại nội dung hoặc sửa chuẩn trích dẫn bằng suy đoán.
- Khôi phục Word từ PDF/ảnh quét.
- Mọi biểu mẫu, hợp đồng, tạp chí hoặc IEEE hai cột.
- Tự sửa mọi thiết kế có khung hoặc tọa độ.
- Tài khoản, thanh toán, lịch sử tài liệu lâu dài và vận hành quy mô lớn.
- API AI trả phí trong luồng bắt buộc.

Ô dán văn bản trực tiếp là hướng mở rộng sau. Hiện tại người dùng lưu nội dung thành DOCX rồi tải lên. Không gọi hỗ trợ nhận DOCX từ nội dung AI là đã có giao diện nhận trực tiếp mọi định dạng Markdown/HTML.

## 5. Mẫu mặc định đề xuất

Tên hiển thị: **Báo cáo phổ thông DocLint**. ID đích: `general`; phiên bản đầu `1.0.0`. Đây là mẫu của dự án, không phải chứng nhận APA/IEEE/HUST.

| Thuộc tính | Đề xuất |
|---|---|
| Trang thường | A4 dọc; không ép section đặc biệt hoặc có vùng bảo vệ |
| Lề | Trái 30 mm; phải/trên/dưới 20 mm |
| Thân bài | Times New Roman, 13 pt, căn đều, giãn dòng 1,5 |
| Khoảng cách | Trước 0 pt, sau 6 pt; thụt đầu dòng 10 mm bằng thuộc tính đoạn |
| Đề mục | Cấp 1: 16 pt; cấp 2: 14 pt; cấp 3: 13 pt; đậm, giữ với đoạn sau |
| Chú thích | 12 pt, nhất quán; vị trí chỉ điều chỉnh khi liên kết với đối tượng đủ rõ và được phép |
| Bảng | Cỡ chữ theo vai trò và không gian, khoảng 11–12 pt khi phù hợp; không gộp/tách ô hoặc đổi dữ liệu |
| Ảnh | Vừa vùng in, giữ tỷ lệ; không phóng lớn mặc định nếu chưa đủ căn cứ |
| Ngắt trang | Tránh đề mục lẻ; không xóa trang trắng hoặc đoạn có cấu trúc chỉ vì ít chữ |

Các con số là đề xuất sản phẩm cần kiểm tra bằng corpus; không phải mọi loại khối đều áp dụng phông và giãn dòng thân bài. Mã nguồn hiện tại chưa có profile `general` này: `hust` đang dùng thụt đầu dòng 1,27 cm và cách trước/sau 6 pt; `report` dùng Calibri 12 pt. Không được nói chỉ đổi tên là đã có đầy đủ mẫu mới.

Mặc định đề xuất là chuẩn hóa bố cục bằng các phép sửa hẹp được kiểm soát; chế độ strict giữ ký tự là tùy chọn rõ ràng. Cần giải thích rằng dọn Space/Tab hoặc đoạn rỗng đã cho phép là thay đổi ký tự trình bày, không tuyên bố mọi ký tự nguồn bất biến trong chế độ layout.

Chỉ đề xuất thêm bìa hoặc mục lục khi phù hợp cấu trúc và tác giả lựa chọn. Mẫu phổ thông không tự biến mọi văn bản ngắn thành báo cáo đầy đủ bìa/mục lục. Chương mới sang trang khác chỉ khi thật sự nhận diện được chương hoặc người dùng yêu cầu, không đặt mọi Heading 1 sang trang mới.

## 6. Trải nghiệm chính

1. Tải DOCX; mẫu mặc định đã được chọn sẵn, có thể đổi.
2. Hệ thống phân tích và chỉ trình bày nhóm chưa chắc chắn hoặc yêu cầu có tác động lớn.
3. Với đề mục mơ hồ: giữ nguyên / thân bài / đề mục ở cấp phù hợp. Không yêu cầu phân loại lại mọi dòng.
4. Người dùng yêu cầu dàn trang; hệ thống tạo và kiểm tra kế hoạch, thực hiện và xác minh.
5. Kết quả có ba nhóm dễ hiểu: **đã sửa / đã giữ nguyên / cần kiểm tra**.
6. Mở thay đổi quan trọng để xem trước/sau, lý do, căn cứ và vị trí khi xác định được.
7. Đổi lựa chọn thì chạy lại từ bản gốc; tải kết quả trong hạn phiên hoặc yêu cầu xóa.

Khi không định vị được trang đáng tin cậy, dẫn bằng trích đoạn/mã khối; không bịa vị trí. Nhật ký kỹ thuật JSON phục vụ đối chiếu, giao diện phục vụ người không biết OOXML.

## 7. Định nghĩa thành công và phép đo

| Chỉ số | Cách đo |
|---|---|
| Vi phạm toàn vẹn | Số lần cổng phát hiện vi phạm và số ứng viên vi phạm bị chặn; không dùng tỷ lệ ca test đạt làm chứng minh không có mọi lỗi chưa biết |
| Đúng vai trò/đề mục | Precision/recall trên tập gán nhãn độc lập, tách theo nguồn/mẫu để giảm trùng lặp |
| Nhất quán trình bày | Số kiểm tra đạt, bỏ qua và không áp dụng, theo từng vai trò trong vùng hỗ trợ |
| Công người dùng | Số nhóm phải xác nhận, số thao tác và thời gian hoàn thành trên tập tài liệu đại diện |
| Tương thích Word | Mở, cập nhật trường, lưu và mở lại trên phiên bản/phông đã ghi nhận |
| Minh bạch | Người thử giải thích được phần nào đã sửa/giữ lại và tìm được thay đổi quan trọng |
| Vận hành | Tỷ lệ lỗi theo giai đoạn, thời gian hàng đợi, tài nguyên và dọn phiên |

Mục tiêu kỹ thuật bắt buộc là không công bố ứng viên đã bị phát hiện vi phạm. Các ngưỡng về độ chính xác, số phút tiết kiệm và hài lòng cần đo baseline rồi chốt; không tự công bố một tỷ lệ đẹp chưa có dữ liệu.

## 8. Những điểm cần nhóm cùng chốt

| Quyết định | Đề xuất để thảo luận |
|---|---|
| Người dùng đầu tiên | Sinh viên/nhóm làm báo cáo tiếng Việt một cột |
| Mẫu mặc định | `general` của DocLint, các mẫu riêng là lựa chọn có nguồn và phiên bản |
| Mức tự động hóa | Tự xử lý khi đủ điều kiện; trường hợp mơ hồ giữ nguyên hoặc hỏi theo nhóm |
| Bìa/mục lục | Tùy chọn phù hợp tài liệu; không chèn bắt buộc vào mọi văn bản |
| Công bố beta | Nhóm nhỏ, giới hạn tài nguyên và phạm vi rõ; mục lục Word chưa nghiệm thu không được quảng cáo đã đúng tuyệt đối |

Các mục này là bản đề xuất có thể chỉnh, không phải giả định rằng người dùng đã phê duyệt một bộ đặc tả bất biến.
