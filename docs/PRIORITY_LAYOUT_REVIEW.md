# Cải tiến theo đánh giá bố cục

Bản này xử lý các nhận xét theo bảy mức ưu tiên. Không dùng API AI. Những nhận xét
trong tài liệu đánh giá được đối chiếu lại với code: một số khác biệt xuất phát từ
tùy chọn giữ định dạng, một số là lỗi nhận diện cần sửa, một số cần giới hạn để bảo
toàn tài liệu. Không cam kết mọi tài liệu Word sẽ có cùng cách phân trang.

## 1. Tính nhất quán

- Một từ dùng Consolas không còn làm cả đoạn mô tả, danh sách FR hoặc đoạn văn bị
  nhận nhầm là code. Chỉ giữ vai trò code khi có style mã nguồn rõ ràng hoặc phần
  lớn văn bản đơn cách kèm dấu hiệu cú pháp.
- Run có character style vẫn được chuẩn hóa phông/cỡ, giữ nhấn mạnh và phông ký hiệu.
- Đoạn có Space/Tab vẫn được chỉnh phông, giãn dòng mà không tự xóa ký tự hoặc đoán
  lại vị trí căn. Vùng được người dùng khóa luôn được ưu tiên.
- Khổ A4 và lề theo mẫu không còn bị bỏ qua chỉ vì cuối tài liệu có phần tham khảo
  hoặc phụ lục. Section ngang/nhiều cột, section có vùng khóa thủ công hoặc section
  nằm bên trong một đoạn khóa vẫn được giữ và có cảnh báo cụ thể.
- Mặc định chuẩn hóa định dạng phần tham khảo/phụ lục, giữ mọi chữ, số và khoảng
  trắng có sẵn. Hai tùy chọn nâng cao cho phép giữ nguyên cả định dạng cũ. Tiêu đề
  phần cuối dùng cùng mẫu, màu và cơ chế sang trang với tiêu đề thân bài.

## 2. Ngắt trang và bảng

- Mục lục có sẵn cũng được tách khỏi bìa và nội dung khi người dùng chọn giữ nó.
  Giữ mục lục cũ không đồng nghĩa đã tính lại số trang: có cảnh báo đề nghị thay
  nếu cần đối chiếu. Giao diện mặc định tạo/thay mục lục khi có đủ tiêu đề.
- Nhận diện cả Tab thật (`w:tab`) trong mục lục gõ tay.
- Dòng dẫn rõ ràng trước danh sách dùng `keepNext`; không tự biến thành mục lục.
- Bảng ngắn có thể giữ các hàng cùng nhau; bảng dài được phép qua trang và tránh
  một hàng cuối bị tách riêng. Hàng tiêu đề được lặp khi đã xác nhận/có sẵn.
- Bảng ô gộp có lưới đầy đủ được định dạng mà không đổi `gridSpan`, `vMerge`, số ô
  hoặc dữ liệu. Bảng lồng, lưới thiếu và bảng chứa đối tượng đặc biệt được giữ.
- Bảng dựng bìa dùng bố cục bìa, không bị áp màu/viền của bảng dữ liệu.
- Không cộng thêm `pageBreakBefore` nếu ngay trước đó đã có ngắt trang thủ công.

## 3. Section và số trang học thuật

Tùy chọn **Học thuật** tách bìa, phần đầu, thân bài và phụ lục khi xác định được:

- Bìa: section riêng, không hiện số trang đầu.
- Mục lục/danh mục và phần có tiêu đề rõ như Tóm tắt/Lời mở đầu: La Mã `i, ii…`.
- Chương 1: bắt đầu từ số `1`. Đoạn mở đầu không có tiêu đề vẫn thuộc thân bài;
  hệ thống cảnh báo, không tự thêm chữ “Lời mở đầu”.
- Phụ lục: section riêng, tiếp tục số Ả Rập của thân bài.

Áp dụng cho một section dọc hoặc bìa đã tách sẵn thành section đầu và phần còn lại
là một section dọc. Tài liệu nhiều section khác, bố cục ngang/nhiều cột, footer
phức tạp/chẵn-lẻ riêng hoặc vùng khóa thủ công không bị ép chuyển; báo cáo ghi rõ
khi yêu cầu số trang chưa hoàn tất. Header/footer sẵn có được giữ nội dung.

## 4. Hình, caption và danh mục

- Caption dùng cỡ 12 pt với mẫu HUST, chữ nghiêng, giữ gần đối tượng khi liên kết rõ.
- Chuỗi số rõ ràng, liên tiếp có thể chuyển sang `SEQ` mà giữ nguyên nhãn đang thấy.
  Nhãn chương vẫn là chữ/số gốc; `SEQ` đếm phần cuối và bắt đầu lại ở chương mới.
  Không tự sửa nhãn trùng, nhảy số, số 0 đầu, nhãn chia run phức tạp hoặc chương xen kẽ.
- Tham chiếu khớp chính xác với một nhãn duy nhất có thể chuyển thành `REF` tới
  bookmark nhãn. Không đoán các cách viết tham chiếu khác hoặc liên kết mơ hồ.
- Danh mục hình/bảng dùng `TOC \c` khi cả nhóm đã chuyển `SEQ`; Word cập nhật từ
  caption. Khi phải giữ số gõ tay, danh mục dùng nhãn đã giữ và có cảnh báo cần
  chạy lại DocLint sau khi sửa tên/số chú thích.
- Danh mục viết tắt chỉ lấy từ cặp `API: giải thích`, `XML = giải thích` hoặc bảng
  mã–giải thích có nhãn rõ trong tài liệu. Không tra cứu/sáng tác nghĩa còn thiếu;
  không tự hợp nhất hai định nghĩa khác nhau.
- Ảnh inline độ phân giải cao đang hiển thị nhỏ được phóng tối đa khoảng 90% vùng
  chữ, có giới hạn chiều cao và mật độ điểm ảnh. Ảnh nhỏ, crop, ảnh nổi/nhóm ảnh
  được giữ hoặc cảnh báo. Không phóng mờ icon, không tự thêm tên hình còn thiếu.

## 5. Bìa

- Phân biệt trường/khoa, tên báo cáo, đề tài, metadata, ghi chú và ngày/địa điểm.
  Câu “Đây là tài liệu tổng hợp…” không còn thành tiêu đề chỉ vì có chữ “báo cáo”.
- Khoảng cách tiêu đề phụ thuộc chiều cao trang và lượng thông tin bìa, thay cho
  một khoảng cố định cho mọi tài liệu.
- Bìa học thuật căn giữa nhất quán, bảng bìa được căn giữa/thu vừa vùng chữ khi an
  toàn. Khi dùng section học thuật, có khung riêng và căn giữa dọc trang bìa.
- Bìa tối giản chủ đích dùng căn trái và phân cấp gọn hơn. Hai mẫu không cần có
  cùng cách căn, nhưng các vai trò trong từng mẫu phải nhất quán.
- Giữ logo đã có và giới hạn kích thước như phần đầu bìa. Không tự bịa logo, tên
  trường, GVHD, địa điểm hoặc năm. Nếu cần các thông tin này, thêm vào file gốc.

## 6. Chi tiết

- Danh sách gõ tay liên tiếp, đơn giản có thể đổi sang `numPr` thật bằng tùy chọn
  nâng cao. Giữ số bắt đầu và dấu `.`/`)`; không đổi danh sách thiếu số hoặc phức
  tạp. Chế độ strict không xóa tiền tố. Mỗi lần chuyển có nhật ký nhãn gốc.
- Code rõ ràng có nền nhẹ, viền trái, phông đơn cách và thuộc tính giữ dòng. Giữ
  nguyên khoảng trắng, Tab, ngắt dòng và mọi ký tự. Có thể tắt qua API `style_code`.
- Chữ ký mặc định giữ vị trí và cảnh báo khi nằm giữa nội dung. Khi có duy nhất
  một khối rõ ràng, tùy chọn nâng cao cho phép chuyển nhãn cùng dòng tên nhận diện
  chắc chắn về cuối thân bài, trước phần tham khảo/phụ lục. Khối mơ hồ hoặc khóa
  không được chuyển một phần.

## 7. Độ bền của DOCX

- Số trang mục lục/danh mục được đối chiếu với PDF theo từng section, gồm cả La Mã.
  Bản Word giữ cache đã kiểm tra, không ép Word cập nhật toàn bộ field khi vừa mở.
  Mục lục vẫn có thể cập nhật thủ công sau khi chỉnh sửa trong Word.
- Không bật lại `updateFields=true` theo gợi ý trong đánh giá: đó là rủi ro đã gây
  sai lệch giữa bản xem trước và phần mềm đọc trong phản ánh trước của người dùng.
- Chuyển trường, chuyển tiền tố danh sách, chuyển chữ ký và đổi ngắt trang thành
  ngắt section là các phép sửa hẹp có nhật ký; không nới cổng kiểm chứng cho mọi
  thay đổi nội dung. Các phần không sửa vẫn phải giữ nguyên byte.
- Footer gốc được giữ có chủ đích để bảo toàn gói, dù section dùng một bản sao đã
  sửa. Không xóa part gốc chỉ vì không còn được đoạn văn tham chiếu trực tiếp:
  nó còn có thể được liên kết hoặc phục vụ khôi phục. Không gọi đây là đã dọn hết
  part mồ côi; thay đổi hợp đồng bảo toàn gói là một việc riêng.

## Nghiệm thu

Các kiểm thử trong `DocLint/tests/test_v1_priorities.py` bao phủ nhận diện code,
font/style, backmatter, khổ giấy và khóa vùng, bảng gộp/lồng, code, ảnh, caption,
SEQ/REF, danh mục, La Mã–Ả Rập, tóm tắt, chữ ký, glossary và ngắt trang.
Chạy cùng toàn bộ bộ kiểm thử, kiểm tra luồng trình duyệt và báo cáo N57 riêng.
Không đưa file cá nhân hoặc kết quả N57 vào repository công khai.

PDF dùng LibreOffice; Microsoft Word có thể phân trang khác theo phiên bản/phông.
Sau khi chỉnh sửa nội dung trong Word, cập nhật field và xem lại trang cuối cùng.
