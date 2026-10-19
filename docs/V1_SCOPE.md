# Phạm vi và nghiệm thu DocLint V1

V1 không có API AI. Mọi phép nhận diện có thể giải thích bằng dấu hiệu và quy tắc; trường hợp chưa chắc cần người dùng duyệt hoặc được giữ nguyên. Tài liệu này mô tả hành vi được triển khai, không phải lời hứa xử lý mọi báo cáo.

| Lỗi/thói quen | Nhận diện và xử lý | Điều kiện bảo vệ/giới hạn | Kiểm chứng |
| --- | --- | --- | --- |
| Copy-paste lẫn phông/cỡ | Đọc style kế thừa, phân loại vai trò, áp style mới và run format có kiểm soát | Giữ nhấn mạnh, phông ký hiệu, chỉ số; không sửa code/OMML | Corpus strict; kiểm tra nội dung/media và mở lại DOCX |
| Tiêu đề giả | Nhãn chương, đề mục, chữ hoa/cỡ nổi bật → đề xuất cấp; chỉ gán khi được duyệt | Không coi mọi đoạn in đậm/ngắn là tiêu đề; giữ chữ và số | Đề mục chưa duyệt giữ nguyên; Heading được duyệt có outline/keepNext |
| Giãn dòng/đoạn | Mẫu riêng cho thân bài, quote, reference, caption và list | Vùng khóa/section đặc biệt giữ nguyên; không ép mọi đoạn một kiểu | Kiểm tra style, lặp lại không phát sinh thay đổi |
| Enter để sang trang | Chuỗi >=2 đoạn thật sự rỗng trước chương cấp 1 đã duyệt → pageBreakBefore | Chế độ layout; không bỏ bookmark, section, đối tượng, ký tự trắng có dữ liệu, đoạn trong ô | Bài protected blank; nhật ký phép xóa được phép |
| Space/Tab căn lề | Tự xử lý các trường hợp đủ rõ; người dùng chọn body/center/right_block/keep cho khối khó | Chỉ đầu đoạn; không cắt Tab/Space giữa nội dung; strict không cho thay | Bài strict/layout, reviewed Tab, code, short alignment |
| Danh sách gõ tay | Kiểu thụt treo; danh sách thật giữ style cung cấp numbering | Không tự xóa tiền tố hoặc đánh lại số | Bài inherited numbering; so sánh ký tự |
| Bảng quá rộng/xấu | Bảng đơn giản: vùng in, cột theo nội dung, đệm/viền/chữ; tiêu đề hàng đầu có xác nhận | Không đổi ô/số liệu; bảng gộp, lồng, có đối tượng đặc biệt giữ/cảnh báo | Bài table widths/header, complex table, corpus |
| Hàng bị cắt | Hàng ngắn dùng cantSplit; hàng cao cố định chuyển mức tối thiểu khi bảng được chuẩn hóa | Không cấm tách toàn bộ hàng dài; kiểm tra Word vẫn cần thiết | XML và PDF; không tuyên bố hiểu mọi chiều cao hàng |
| Ảnh tràn/méo | Ảnh inline vừa vùng in cả hai chiều; giữ tỷ lệ hiện tại; cảnh báo lệch tỷ lệ so ảnh gốc | Không phóng ảnh nhỏ; không đổi neo/wrap/nhóm nhiều ảnh/crop tự động | Bài image ratio/media, portrait height |
| Chú thích xa đối tượng | Liên kết đối tượng liền kề duy nhất hoặc lựa chọn của người dùng; keepNext/keepLines | Không di chuyển tùy tiện, không đổi số/tên; tên bảng sau bảng có cảnh báo | Bài caption ambiguity, dựng và xem trang |
| Mục lục gõ tay/sai | Nhận diện vùng cũ, thay khi được duyệt; tạo trường TOC và đối chiếu cache trang <=3 lượt | Không xóa vùng mơ hồ; thiếu dữ kiện/trang chưa ổn định thì partial/cần Word cập nhật | Bài manual TOC, field updateable, tích hợp PDF số trang |
| Footer/số trang | Tạo phần footer riêng và sao chép quan hệ ảnh/liên kết, giữ nội dung/part gốc, tùy chọn trang đầu ẩn | Giữ số trang gốc và báo partial nếu section phức tạp, footer chẵn/lẻ riêng, field lồng nhau hoặc quan hệ bị thiếu; chưa cung cấp mọi phối hợp La Mã–Ả Rập | Bài footer/header, ảnh và hyperlink, header ẩn, package relationship, PDF label |
| Bìa dựng thủ công | Xác nhận vùng, áp mẫu học thuật/tối giản theo thông tin sẵn có | Mặc định giữ; không bịa logo/tên/ngày; bảng dựng bìa giữ cấu trúc | Bài cover boundary, ký tự không đổi; duyệt trang |
| Tiêu đề lẻ/trang thưa | Thuộc tính giữ đoạn; PDF định vị tiêu đề gần cuối trang và trang ít chữ | Không xóa trang trắng có chủ đích hoặc thu nhỏ chữ để bớt trang | PDF cảnh báo có số trang; không coi heuristic là chứng nhận tuyệt đối |
| Nội dung vượt vùng in | Đối chiếu text/image bounds của PDF với giới hạn định vị được | Phụ thuộc khớp section/trang; đầu/chân trang loại khỏi kiểm tra lề ngang | Warnings print_area; người dùng xem lại, không sửa mất nội dung |
| Section ngang/nhiều cột | Lập bản đồ trước khi đổi hình học trang | Giữ section đặc biệt và section có vùng khóa; không chuyển IEEE tự động | Corpus landscape; exact region locks |
| Tham khảo, code, math, revision | Phân loại, khóa vùng tùy chọn; bỏ qua cấu trúc rủi ro | Không sửa chuẩn trích dẫn, mã hoặc công thức | OMML/text/media corruption injection, code whitespace, refs/appendices |

## Cổng kiểm chứng

1. Các lựa chọn phải tham chiếu đúng mã khối và nằm trong danh sách hành động cho phép.
2. Vùng khóa phải nguyên cấu trúc và thuộc tính.
3. Cấu trúc/nội dung ngoài thuộc tính trình bày phải khớp snapshot kỳ vọng.
4. Snapshot nội dung chỉ tiến lên bằng phép sửa có phạm vi rõ và đã được chấp thuận.
5. Phần XML mới, quan hệ và phần đính kèm phải được đăng ký; byte của phần không sửa phải giữ nguyên.
6. Kiểm tra lặp lại trên ZIP đã đóng gói, không chỉ kiểm tra cây trong bộ nhớ.
7. PDF và số trang có trạng thái kiểm tra riêng; lỗi dựng không được mô tả là đã xác minh.

Không được kết luận một DOCX bất kỳ an toàn/đẹp chỉ từ corpus, một điểm số hay một lần render. V1 vẫn cần đánh giá người dùng thật và Word thực trên các bộ phông mục tiêu.

## Chưa làm trong V1

- Chuyển sang IEEE hai cột; mọi kiểu biểu mẫu, hợp đồng và bố cục tạp chí.
- Viết lại/dịch/tóm tắt nội dung, kiểm tra đạo văn hoặc sửa trích dẫn học thuật.
- Đánh lại toàn bộ số hình/bảng và tham chiếu chéo.
- Biến mọi danh sách gõ tay thành numbering tự động.
- Tự di chuyển ảnh nổi, gộp/tách ô, tái cấu trúc bảng phức tạp.
- Cam kết bộ dựng LibreOffice giống Word từng điểm ảnh.
- Đo mức hài lòng hoặc “wow” của người dùng khi chưa có thử nghiệm người dùng.

## Mẫu nghiệm thu thủ công

Dùng báo cáo mẫu trong giao diện, duyệt Heading và hàng tiêu đề bảng, chọn chế độ layout, dàn bìa, tạo TOC và số trang. Xem cả trang đầu, trang thân bài có bảng/ảnh, trang mục lục và trang cuối. Mở Word để kiểm tra field cập nhật, phông, ảnh, ngắt trang, công thức. Dùng file vốn đã đẹp để xác nhận hệ thống không sửa nhiều vô ích. Tài liệu cá nhân chỉ được đưa vào bộ dữ liệu khi có sự cho phép riêng; bản gửi trong chat không được commit thành fixture.
