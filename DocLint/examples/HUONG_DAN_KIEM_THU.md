# Bộ tệp kiểm thử DocLint V1

Bộ này xuất các mẫu tổng hợp từ bộ kiểm thử của DocLint tại mã nguồn
`3c4c1bc22f2cb55f06c0039cffaafc54bdf48216`. Không chứa tài liệu người dùng đã tải lên.
Các tệp mẫu cố ý có lỗi bố cục hoặc cấu trúc cần được giữ nguyên.

## Bắt đầu trên Windows

1. Giải nén `bo-kiem-thu-doclint-v1.zip` bằng **Extract All / Giải nén tất cả**.
2. Chạy web DocLint như thường lệ bằng `RUN_DOCLINT.cmd` trong thư mục mã nguồn.
   Bộ mẫu này không thay thế thư mục mã nguồn và không cần cài thêm thư viện.
3. Trên web, tải lên một tệp trong `01_DAU_VAO_DE_THU`. Bắt đầu với tệp **02**.
4. Chọn các thiết lập theo bảng bên dưới rồi bấm dàn trang.
5. Tải Word kết quả xuống, mở bằng Microsoft Word hoặc LibreOffice Writer.
   So sánh với bản gốc và kết quả tham chiếu trong `02_KET_QUA_THAM_CHIEU`.
   Không tải các tệp kết quả tham chiếu lên thay cho đầu vào khi thử lần đầu.

## Năm mẫu dễ thử

| Tệp trong 01_DAU_VAO_DE_THU | Cần kiểm tra | Cách chọn và kết quả mong đợi |
| --- | --- | --- |
| `01_bao_cao_nhieu_loi_bo_cuc.docx` | Mẫu tổng hợp đang có trên web: định dạng thiếu nhất quán, tiêu đề, bảng và các thành phần báo cáo | Dùng chế độ dàn trang, chọn một mẫu trình bày. Nhận diện tự động 9 tiêu đề; chỉ 1 câu hỏi xác nhận nhóm đầu bảng. Kiểm tra bảng, hình, các con số và chữ gốc sau khi xuất. |
| `02_bia_muc_luc_noi_dung.docx` | Bìa có nhiều dòng trống, tiếp theo là đoạn mở đầu và chương 1 | Chọn mẫu HUST, chế độ dàn trang, **Bìa học thuật — trang riêng**, giữ ranh giới bìa được đề xuất, **Tạo mục lục — trang riêng**, bật số trang và ẩn số trang đầu. Bản PDF tham chiếu có 3 trang: bìa → mục lục → nội dung. Đoạn mở đầu phải thuộc trang nội dung. |
| `03_bia_da_co_ngat_trang.docx` | Tương tự tệp 02 nhưng bìa đã có ngắt trang thủ công | Chọn mẫu HUST, chế độ dàn trang, **Bìa tối giản — trang riêng**, giữ ranh giới bìa được đề xuất, tạo mục lục riêng; giữ số trang hiện tại. PDF tham chiếu có 3 trang; không xuất hiện thêm trang trắng giữa bìa và mục lục. |
| `04_hai_muoi_dong_de_nham_tieu_de.docx` | 20 dòng đánh số in đậm, có thể là danh sách hoặc đề mục | Web hỏi **1 nhóm** thay vì 20 câu hỏi riêng. Thử giữ nguyên lần đầu, rồi thử xác nhận là tiêu đề trong lần tiếp theo. Không tự động chuyển toàn bộ thành tiêu đề khi chưa chọn. |
| `05_ba_chuong_ro_rang.docx` | Ba chương in đậm, đánh số tăng dần, mỗi chương có thân bài | Tự nhận diện 3 tiêu đề, không cần hỏi về tiêu đề. Để so với tham chiếu: chọn mẫu HUST, chế độ dàn trang, giữ bìa hiện tại, tạo mục lục riêng, giữ số trang hiện tại. Mục lục phải có đủ 3 chương và không thay chữ trong thân bài. |

Các tên `COVER_SENTINEL`, `INTRODUCTION_SENTINEL`, `SECTION_SENTINEL`,
`BODY_SENTINEL` trong tệp 02–03 là chữ đánh dấu có sẵn của mẫu kiểm thử:

- `COVER_SENTINEL` chỉ nằm trên bìa, không được đưa vào danh sách mục lục.
- `INTRODUCTION_SENTINEL` và `BODY_SENTINEL` nằm ở phần nội dung sau mục lục.
- `SECTION_SENTINEL` là tiêu đề chương, được liệt kê trong mục lục.

## Kết quả tham chiếu

Thư mục `02_KET_QUA_THAM_CHIEU` có kết quả cho tệp **02, 03, 05**:

- `.docx`: Word đã dàn trang bằng mã nguồn nêu trên.
- `.pdf`: bản dựng bằng LibreOffice trên Linux để đối chiếu bố cục.
- `.json`: báo cáo xử lý, trong đó có thiết lập đã dùng và kết quả kiểm tra toàn vẹn.

Đây là kết quả chạy thực tế, không phải ảnh minh họa. Microsoft Word và LibreOffice
có thể phân trang khác nhau tùy phiên bản và phông chữ. Nếu Word yêu cầu cập nhật
mục lục, bấm chuột phải vào mục lục → **Update Field / Cập nhật trường**.
Không cần kết quả giống từng điểm ảnh; cần đúng cấu trúc và bảo toàn nội dung.

## Ba mươi mẫu nâng cao

`03_MAU_NANG_CAO` chứa `case_00.docx` đến `case_29.docx`, sinh từ
`DocLint/tests/v1_fixtures.py`. Tất cả có tiếng Việt, số `0012`, `3,14`, `3.14`,
bảng, danh sách, tài liệu tham khảo và phụ lục. Tùy mã case còn có bìa, ảnh,
ô gộp, công thức, mã nguồn, bookmark, lịch sử sửa đổi hoặc trang ngang.

- Thử `case_00.docx` để kiểm tra nhiều thành phần cùng lúc.
- Thử `case_04.docx` để kiểm tra ảnh rộng và chú thích.
- Thử `case_07.docx` để kiểm tra bảng có ô gộp.
- Thử `case_08.docx` để kiểm tra khoảng trắng trong mã nguồn.
- Thử `case_11.docx` để kiểm tra phần trang ngang.

Ảnh trong bộ này là ảnh thử rất nhỏ, có thể trông như một ô màu khi được phóng to.
Không dùng nó để đánh giá chất lượng ảnh thực tế. Danh sách thành phần từng tệp
nằm trong `DANH_SACH_TEP.json`.

Các mẫu nâng cao đã được kiểm tra bằng bộ máy dàn trang và đối chiếu toàn vẹn;
không khẳng định đã kiểm tra trực quan đủ 30 tệp bằng Microsoft Word trên Windows.
Hệ thống có thể giữ nguyên vùng phức tạp và đưa cảnh báo để tránh làm hỏng tài liệu.

## Khi nào coi là đạt?

- Tệp được tải lên và tải kết quả xuống bình thường.
- Chỉ có câu hỏi khi hệ thống còn phân vân; các mục tương đương được gom chung.
- Bìa, mục lục, nội dung tách trang đúng khi chọn các thiết lập tương ứng.
- Không mất chữ, số, bảng, hình, công thức; không tự viết lại câu văn.
- Khoảng trắng có ý nghĩa trong mã nguồn và nội dung được bảo vệ không bị xóa.
- Báo cáo xử lý xác nhận toàn vẹn; cảnh báo chưa kiểm chứng được phải được hiển thị.

Nếu có lỗi, ghi tên tệp mẫu, các thiết lập đã chọn, ảnh chụp kết quả và tải nhật ký
chẩn đoán/báo cáo JSON trên web để gửi lại. Đừng chỉ ghi “không đẹp”: ví dụ
“tệp 03 có trang trắng trước mục lục” sẽ giúp xác định lỗi nhanh hơn.
