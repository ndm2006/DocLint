# 02 — Yêu cầu, điều kiện nghiệm thu và truy vết

**Dự thảo 0.1.** Tiền tố `BP-FR` phân biệt yêu cầu trong blueprint với danh mục FR của báo cáo cuối kỳ. Các yêu cầu hiện có và phần đề xuất được đánh dấu riêng.

## 1. Ca sử dụng

| Mã | Tác nhân | Mục tiêu và điều kiện hoàn tất |
|---|---|---|
| UC-01 | Tác giả | Tải DOCX; được cấp phiên nếu hợp lệ hoặc nhận lý do từ chối rõ |
| UC-02 | Tác giả | Nhận phân tích và duyệt chỉ những nhóm cần xác nhận |
| UC-03 | Tác giả | Chọn/giữ mẫu, dàn trang và nhận kết quả có kiểm chứng |
| UC-04 | Tác giả | Xem thay đổi, vùng giữ nguyên, cảnh báo và bản xem trước khả dụng |
| UC-05 | Tác giả | Tải đúng sản phẩm của lần chạy hợp lệ hiện tại |
| UC-06 | Tác giả | Đổi lựa chọn và xử lý lại từ bản gốc |
| UC-07 | Tác giả | Hủy/xóa phiên; được thu hồi truy cập đúng vòng đời |
| UC-08 | Người vận hành | Kiểm tra năng lực môi trường, lỗi và giới hạn qua công cụ vận hành; không giả định có cổng quản trị web |

Backend, hàng đợi và bộ dọn dữ liệu là thành phần bên trong, không phải người dùng nghiệp vụ. LibreOffice là phụ thuộc bên ngoài của bộ dựng, không phải người có quyền duyệt tài liệu.

## 2. Yêu cầu chức năng và điều kiện nghiệm thu

| Mã | Yêu cầu | Điều kiện nghiệm thu | Hiện trạng |
|---|---|---|---|
| BP-FR-01 | Kiểm tra đầu vào và tài nguyên | Sai loại, ZIP/XML lỗi, vượt giới hạn bị từ chối trước chỉnh sửa; có thông báo phù hợp | Đã có nền tảng |
| BP-FR-02 | Phân tích vai trò và vùng bảo vệ | Phân biệt thân bài/đề mục/đối tượng; không dùng in hoa hoặc in đậm như bằng chứng duy nhất; xử lý thuộc tính kế thừa | Đã có, cần mở corpus |
| BP-FR-03 | Mẫu mặc định và cấu hình hiệu lực | UI, API và bộ xử lý dùng cùng cấu hình đã phân giải, có ID/phiên bản; mẫu không đủ nguồn không nhận là chuẩn chính thức | Mới có hai preset; hợp đồng mới đề xuất |
| BP-FR-04 | Duyệt nhóm mơ hồ | Ba lựa chọn khác nghĩa; giữ nguyên phải thật sự giữ; không hiện toàn bộ đoạn; quyết định gắn đúng phân tích nguồn | Đã có ba lựa chọn; version binding đề xuất |
| BP-FR-05 | Kế hoạch thay đổi có kiểm soát | Mỗi phép sửa có đích, tiền điều kiện, rule, lý do; không xung đột hoặc vượt khóa; kế hoạch gắn phiên bản | Ghi thay đổi trong Editor đã có; ChangePlan độc lập đề xuất |
| BP-FR-06 | Chạy lại từ nguồn bất biến | Mọi lần chạy cùng phiên đọc original; thay lựa chọn không tích lũy sửa đổi cũ; chặn yêu cầu cạnh tranh/lựa chọn cũ | Đã có gốc/revision; mở rộng snapshot đề xuất |
| BP-FR-07 | Kiểm tra và dựng xem trước | Nội dung/vùng khóa được kiểm tra trước và sau; lỗi PDF không được ghi như đã kiểm chứng trang | Đã có nền tảng |
| BP-FR-08 | Giải thích thay đổi | Phân biệt phát hiện/đề xuất/áp dụng/bỏ qua; giải thích trước/sau; trích đoạn hoặc trang có căn cứ | JSON và thay đổi đã có; UX/chuẩn sự kiện mới đề xuất |
| BP-FR-09 | Xuất bản sản phẩm | Chỉ đúng revision/run đã qua cổng; gói DOCX mở hợp lệ; ứng viên lỗi không lộ qua download | Cổng tải đã có; run manifest đề xuất |
| BP-FR-10 | Vòng đời phiên | Hết TTL bị chặn; hủy dừng tác vụ trước khi xác nhận xóa; dọn khi dịch vụ hoạt động/khởi động lại | Đã có nền tảng |
| BP-FR-11 | Tiến độ và kết quả trung thực | Tách trạng thái công việc và trạng thái kiểm tra; bảo tồn toàn tệp không báo đã sửa toàn bộ | Đã có ready/partial/checks; hoàn thiện cách giải thích |
| BP-FR-12 | Thành phần trình bày tùy chọn | Không tạo bìa/TOC thiếu thông tin; không đoán số trang; Word cập nhật trường được kiểm tra trước tuyên bố tương thích | Đã có xử lý có điều kiện; còn nghiệm thu Word |

## 3. Yêu cầu chất lượng

- **An toàn sửa đổi:** INV-01 đến INV-08 là cổng chặn, không phải điểm thưởng có thể bù bằng bố cục đẹp.
- **Tái lập:** cùng nguồn, lựa chọn, profile/ruleset/engine và môi trường dựng được ghi lại; sai khác về phông/bộ dựng phải có cảnh báo. Không cam kết mọi lần dựng tạo byte PDF giống nhau.
- **Dễ mở rộng:** luật không truy cập HTTP/hàng đợi; UI không chứa bản sao thuật toán phân cấp; profile không chứa mã thực thi.
- **Dễ dùng:** trình bày nhóm liên quan, mặc định hợp lý, thông báo hướng khắc phục thay vì tràn chi tiết XML.
- **Tài nguyên:** giữ giới hạn hiện tại cho beta: 15 MiB upload, 80 MiB giải nén, 8 MiB/XML, 2.000 mục ZIP, 5.000 khối trực tiếp; 1 worker, 4 việc chờ, 10 upload/IP/phút, 10 lần dàn trang/phiên; tối đa 120 trang preview, 60 giây/lượt Office, 3 lượt đối chiếu TOC.
- **Dữ liệu tạm:** TTL 30 phút từ lúc nhận; không tự gia hạn; không đưa tài liệu người dùng vào Git/log/backup thông thường. UUID hiện là quyền truy cập phiên, không phải hệ thống tài khoản.
- **Chi phí:** luồng bắt buộc không cần API AI trả phí; hạ tầng vẫn có chi phí hoặc giới hạn thời gian nếu dùng máy cá nhân/hosting thử nghiệm.

Các giới hạn trên là cấu hình hiện tại, không phải benchmark thời gian xử lý hoặc số người đồng thời đã được chứng minh.

## 4. Bộ tình huống nghiệm thu tối thiểu

| Mã | Tình huống và kết quả mong đợi |
|---|---|
| AC-01 | DOCX sai cấu trúc/vượt giới hạn: không chạy editor; báo lỗi có ích |
| AC-02 | Báo cáo ghép nhiều nguồn: vai trò đã chắc nhận mẫu thống nhất, nhấn mạnh có nghĩa được giữ |
| AC-03 | Dòng viết hoa là tên chủ đề: không bị tự đổi thành đề mục; giữ nguyên/đổi vai trò có đúng ý nghĩa |
| AC-04 | Nhiều BÀI TẬP và chuỗi số bắt đầu lại: cấp cha–con đúng trên bộ gán nhãn |
| AC-05 | Bìa case 00: phạm vi bìa và căn giữa đúng; trang ngang cần giữ không bị đổi |
| AC-06 | Bảng gộp/ảnh inline/công thức: dữ liệu, topology và đối tượng không mất; kích thước chỉ đổi khi đủ điều kiện |
| AC-07 | Trộn khung và văn bản theo luồng: vùng khóa và ảnh hưởng kế thừa giữ đúng; ngoài vùng vẫn có thể sửa |
| AC-08 | Tài liệu toàn bố cục cố định: trả byte gốc theo chính sách, giải thích chỉ bảo tồn |
| AC-09 | Cố ý gây thay đổi ngoài kế hoạch: kiểm tra bắt lỗi và endpoint không xuất ứng viên đó |
| AC-10 | Dựng PDF thất bại/TOC không giải được trang: không bịa số; trạng thái một phần; DOCX an toàn vẫn có thể trả theo fallback đã định nghĩa |
| AC-11 | Đổi lựa chọn, gửi hai yêu cầu, dùng quyết định cũ: nguồn không tích lũy, revision cũ bị từ chối/được yêu cầu duyệt lại |
| AC-12 | Hủy, hết hạn, khởi động lại: dừng việc, thu hồi quyền truy cập và dọn đúng vòng đời |
| AC-13 | Mở Word → cập nhật mục lục → lưu → mở lại: số trang và trường hợp lệ trên môi trường ghi nhận |
| AC-14 | Nhật ký: chỉ ghi đã áp dụng khi có kết quả thực; mọi phép sửa có rule/reason; vị trí không xác định được phải ghi rõ |
| AC-15 | Thêm profile bằng cấu hình hợp lệ: đúng role style, UI/API cùng mặc định, alias cũ không hỏng; cấu hình lạ bị từ chối |

AC là đặc tả kiểm thử cần đối chiếu mã, không tuyên bố tất cả đã được kiểm thử hoặc đã đạt ở hiện tại. Với AC-10, nếu không có cách tạo mục lục mới an toàn khi thiếu renderer, bỏ qua thao tác đó và cảnh báo; không lấy “partial” làm lý do xuất DOCX vi phạm toàn vẹn.

## 5. Ma trận truy vết rút gọn

| Vấn đề | Yêu cầu | Thành phần đích | Sơ đồ | Kiểm chứng |
|---|---|---|---|---|
| Tốn thời gian chỉnh nhiều nguồn | 02, 03, 05 | Analyzer, ProfileResolver, Planner | D03, D04, D05 | AC-02, AC-15; đo thử dùng |
| Nhận sai đề mục/bìa | 02, 04, 12 | Hierarchy/Cover detectors, Review | D02, D03, D06 | AC-03, AC-04, AC-05 |
| Hỏng cấu trúc hoặc mất đối tượng | 05, 07, 09 | ProtectionPolicy, Applier, IntegrityGate | D04, D05, D10 | AC-06 đến AC-09 |
| Không biết đã sửa gì | 08, 11 | AuditProjection, ResultPresenter | D02, D05, D06 | AC-14; người thử giải thích được |
| Chạy lại/phiên bị lỗi | 06, 10, 11 | JobService, JobStore, Queue | D05, D07, D08 | AC-11, AC-12 |
| PDF đúng nhưng Word sai | 07, 12 | Renderer, PaginationFinalizer, compatibility tests | D03, D05 | AC-10, AC-13 |

Trong bảng, số 02 là BP-FR-02 và tương tự. Mỗi issue/PR phải liên kết một yêu cầu, ít nhất một AC hoặc bằng chứng phù hợp và ảnh hưởng tới các ràng buộc.

## 6. Definition of Ready và Definition of Done

**Sẵn sàng lập trình:** có tình huống thật hoặc mẫu tái hiện; nêu kết quả muốn có; xác định phạm vi được đổi/không được đổi; có AC, thành phần sở hữu và tác động dữ liệu/API; đã xem có xung đột INV nào không.

**Hoàn thành:** kết quả đạt AC và cổng bảo toàn; kiểm thử trực tiếp ảnh hưởng và hồi quy cần thiết đạt; lỗi/partial được trình bày trung thực; API/profile/schema tương thích hoặc có kế hoạch chuyển tiếp; tài liệu và bằng chứng cập nhật; giới hạn đã biết ghi rõ.

Không yêu cầu viết test chỉ để phản chiếu từng dòng mã. Ưu tiên kiểm tra quyết định nghiệp vụ, phản ví dụ, đường lỗi, an toàn và tích hợp có nguy cơ hồi quy.
