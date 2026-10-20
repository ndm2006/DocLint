# Giữ vùng bố cục đặc biệt và sửa phần văn bản độc lập

## Nguyên nhân và phạm vi

Một DOCX có thể chứa đoạn văn chảy theo trang hoặc nhiều khung chữ có tọa độ,
độ rộng và chiều cao riêng. Tăng cỡ chữ/giãn dòng trong một khung trong khi giữ
tọa độ không bảo đảm chữ vẫn vừa khung. Đối chiếu chữ không chứng minh bố cục
được bảo toàn.

`v1/layout_guard.py` nhận diện framePr trực tiếp/kế thừa, textbox và bảng nổi.
Khung đặt theo trang được bảo vệ cùng vùng chứa nó, chia theo ngắt trang thật,
Page Break Before hoặc section không liên tục. Không dùng lastRenderedPageBreak
làm ranh giới. Ngắt trang trong textbox hoặc ô bảng không chia luồng văn bản chính.
Nếu thiếu ranh giới rõ, phạm vi bảo vệ được mở rộng thay vì đoán vùng có thể sửa.

Các textbox gắn với ảnh/đoạn bằng vị trí theo paragraph/line hoặc inline được giữ
riêng cùng đoạn chứa chúng. Chúng không làm mất nhận diện đề mục ở các đoạn khác.

## Các lớp kiểm chứng

- Đoạn/vùng được giữ có khóa XML chính xác, bao gồm thuộc tính định dạng.
- Section chứa vùng cố định được giữ nguyên, tránh thay lề và kích thước trang
  nhưng vẫn để tọa độ khung cũ.
- Có vùng bố cục cố định: bỏ qua dựng lại bìa/mục lục, số trang, danh mục, caption
  field, chuyển danh sách và chuyển chữ ký; nêu rõ trong nhật ký.
- Tài liệu hoàn toàn là khung: trả lại đúng byte tệp đầu vào, không thêm style hay
  field; operation_mode=preserve_only, status=partial, changed_items=0.
- Tài liệu hỗn hợp: định dạng phần đủ điều kiện bên ngoài; operation_mode=selective.
  Kiểm tra nội dung và vùng khóa vẫn là điều kiện bắt buộc trước khi xuất.

Đây là bảo vệ vùng, không phải công cụ tái dựng tài liệu chuyển từ PDF thành văn
bản chảy. Việc định dạng phần văn bản được phép sửa vẫn có thể làm phần đó đổi
số trang; không cam kết giữ số thứ tự vật lý của mọi trang trong tài liệu hỗn hợp.

## Ba lựa chọn cho dòng chưa rõ vai trò

| Lựa chọn | Trường API | Hành vi |
| --- | --- | --- |
| Giữ nguyên định dạng | unchanged_candidates | Khóa chính xác đoạn; giữ khổ/lề dùng chung |
| Chuẩn hóa thành văn bản thường | preserved_candidates | Định dạng thân bài/danh sách; giữ chữ và tiền tố |
| Dùng làm đề mục | heading_levels | Gán Heading/outline ở cấp đã duyệt |

Tên preserved_candidates cũ được giữ để tương thích API; giao diện không còn
dùng chữ “Giữ nguyên” để gọi thao tác chuẩn hóa thành đoạn thường.

## Bìa

Nhận diện các nhãn tổ chức, báo cáo/essay, đề tài/topic và thông tin người thực
hiện bằng tiếng Việt/Anh. Ngắt trang thật được ưu tiên trước Heading dùng để
trang trí bìa, với điều kiện chưa gặp chương, phần mở đầu hoặc đoạn thân bài.
Cả mẫu học thuật và tối giản đều căn giữa đoạn văn bìa có thể chỉnh. Dòng có
field/công thức/đối tượng được giữ và có cảnh báo; vùng khung chịu chính sách
bảo vệ ở trên. Chọn giữ bìa vẫn có nghĩa giữ định dạng hiện tại.

Kiểm thử hồi quy dùng dữ liệu tổng hợp trong test_v1_layout_guard.py, gồm case_00,
khung kế thừa style, textbox theo đoạn/trang, ngắt trang trong textbox, tài liệu
hỗn hợp, toàn khung và ba cách xử lý đề mục. Tệp cá nhân không được đưa vào Git.
