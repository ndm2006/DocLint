# 03 — Kiến trúc và hợp đồng mở rộng

## 1. Kiến trúc đích

Giữ **ứng dụng nguyên khối có phân mô-đun**, phù hợp nhóm hai người. UI, API, điều phối và xử lý là các trách nhiệm tách biệt nhưng có thể cùng triển khai trong một dịch vụ. Chỉ tách dịch vụ khi có vấn đề đo được và đã xác định cách chia sẻ công việc, tệp, hủy và TTL.

Thứ tự phụ thuộc đề xuất:

1. **Giao diện:** hiển thị cấu hình hiệu lực, nhóm duyệt, tiến độ và kết quả.
2. **Ứng dụng:** điều phối ca sử dụng, phiên, revision, hàng đợi và công bố sản phẩm.
3. **Nghiệp vụ tài liệu:** nhận diện, chính sách bảo vệ, phân giải profile, lập/kiểm tra kế hoạch, quy tắc toàn vẹn.
4. **Adapter:** đọc/ghi OOXML, lưu tệp, LibreOffice/PDFium, đồng hồ và thông tin môi trường.

Nghiệp vụ định nghĩa các cổng cần dùng; adapter hiện thực cổng đó. Luật nhận diện không phụ thuộc FastAPI, đường dẫn ổ đĩa, lệnh Office hay DOM của trình duyệt. UI không tự quyết định lại cấp đề mục bằng một thuật toán khác với backend.

## 2. Ánh xạ hiện tại → đích

| Mã hiện tại | Có thể giữ | Phần chuyển tiếp đề xuất |
|---|---|---|
| `analysis.py`, `hierarchy.py`, `cover.py` | Dấu hiệu, vai trò, quan hệ và các ca hồi quy | Trả AnalysisSnapshot có phiên bản, evidence và ranh giới bảo vệ |
| `layout_guard.py` | Phát hiện và bảo vệ cấu trúc cố định | Chuẩn hóa ProtectionPolicy dùng chung cho mọi rule/operation |
| `core/profiles.py`, `design.py` | Hai preset và cách tạo style riêng | ProfileRegistry/Resolver có role styles và đơn vị rõ; giảm các nhánh đặc biệt theo ID |
| `editor.py` | Các thao tác OOXML đã kiểm chứng | Tách dần planner và applier; đầu tiên bọc như LegacyEngineAdapter |
| `package.py` / IntegrityLedger | Snapshot và kiểm tra phần gói/vùng khóa | Cổng kiểm chứng độc lập nhận kế hoạch và tập thao tác cho phép |
| `pipeline.py`, `fields.py` | Điều phối, dựng, đối chiếu trang có giới hạn | FormatService và PaginationFinalizer qua hợp đồng ổn định |
| `renderer.py` | Cách cô lập Office, dựng/đọc PDF, chẩn đoán | PreviewRenderer/PaginationInspector ports |
| `jobs.py`, `routes.py` | TTL, revision, hàng đợi và cổng download | Đưa việc điều phối vào JobService; API chỉ nhận/trả DTO |
| `static/app.js` | Luồng ba bước, nhóm lựa chọn, xem kết quả | Dùng effective defaults từ backend; thêm AuditProjection dễ hiểu |

Không chuyển toàn bộ thuật toán cùng lúc. Chỉ đưa một nhóm chức năng qua hợp đồng mới sau khi đã có test đặc trưng; so sánh hành vi với đường hiện tại rồi mới chuyển tiếp.

## 3. Hợp đồng dữ liệu

Các tên dưới đây là mô hình đích; một số đã có dạng gần tương đương trong mã, chưa phải các lớp hiện thực đầy đủ.

### AnalysisSnapshot

- `schema_version`, `analysis_id`, `analyzer_version`, `original_sha256`.
- `blocks`: mã trong snapshot, tham chiếu OOXML, vai trò/cấp, thuộc tính hiệu lực, evidence, nhận định certain/ambiguous/protected.
- `regions`, `section_map`, `protection_scopes`, `review_groups`, `findings`.

Mã khối chỉ có nghĩa trong nguồn và snapshot tương ứng. Không coi số thứ tự đoạn là ID vĩnh viễn sau khi chèn/xóa. “Certain” là phân loại theo quy tắc đã kiểm chứng, không phải xác suất 99% nếu chưa hiệu chỉnh bằng dữ liệu.

### EffectiveProfile

- `profile_id`, `profile_version`, `schema_version`, `source`, `scope`, `effective_hash`.
- Trang, style theo vai trò, ngoại lệ và mặc định tùy chọn đã phân giải.
- Đơn vị dùng rõ ràng: mm, pt, hệ số giãn dòng. Adapter chuyển sang twips/half-points ở một chỗ.
- Trường không biết, giá trị không hợp lệ, capability chưa hỗ trợ bị từ chối; không chạy mã từ JSON.

Frontend lấy profile và mặc định này từ backend. Profile được resolve một lần cho một run; không đọc lại cấu hình đang thay đổi giữa chừng. Đổi profile phải đổi phiên bản/hash và lập kế hoạch lại.

### DecisionSet

- `analysis_id`, `original_sha256`, `decision_revision`.
- Quyết định theo nhóm/khối, vùng giữ nguyên, lựa chọn thành phần bổ sung.
- Backend xác nhận mọi đích còn tồn tại và hành động thuộc danh sách cho phép.

Quyết định cũ trên snapshot khác không được tự áp lên khối mới. Trả lỗi xung đột hoặc yêu cầu duyệt lại; không đoán ý định từ vị trí gần giống.

### ChangePlan và Operation

Plan chứa ID/hash nguồn, phân tích, quyết định, profile, ruleset, engine; danh sách operation; phần bỏ qua và cảnh báo.

Mỗi operation gồm:

- `operation_id`, `rule_id`, `rule_version`, loại thao tác và đích rõ ràng.
- Giá trị kỳ vọng trước sửa và giá trị/thuộc tính sau sửa.
- Tiền điều kiện, phạm vi đọc/ghi, ảnh hưởng tới phần dùng chung.
- Lý do, evidence, quyết định người dùng liên quan nếu có.
- Tác động tới nội dung, tính thuận nghịch nếu hỗ trợ, phép dọn ký tự cụ thể nếu có.

Các loại thao tác ban đầu có thể là gán style đoạn, đặt khoảng cách, đổi hình học section, đổi kích thước ảnh inline, chỉnh grid bảng đơn giản và dọn whitespace đã cho phép. Loại thao tác mới cần hỗ trợ trong applier và validator; không thể chỉ thêm tên trong JSON rồi coi là an toàn.

Kế hoạch đã bắt đầu áp dụng không được sửa âm thầm. Khi có thêm dữ kiện phân trang, tạo phần bổ sung có ID/hash và tham chiếu kế hoạch trước; kiểm tra phạm vi, xung đột và toàn vẹn lại. Manifest cuối ghi chuỗi kế hoạch và thao tác thực tế. Một vòng cập nhật trang không được tự làm mất dấu phiên bản của vòng trước; số vòng vẫn có giới hạn.

### Run, AuditEvent và ArtifactManifest

Run gắn revision và toàn bộ fingerprint nêu trên. AuditEvent phân biệt `detected`, `proposed`, `applied`, `skipped`, `failed`, có đích, lý do và kết quả kiểm tra. Audit không được ghi applied khi applier chưa thực hiện thành công.

Manifest ghi artifact, run/revision, SHA-256, kiểu tệp và trạng thái kiểm chứng. Công bố nguyên tử sau cổng cuối; download chỉ phục vụ manifest của run hiện tại đã được phép. Hủy hoặc kết quả run cũ không được ghi đè sản phẩm mới.

Nhật ký theo phiên tạm thời phục vụ người dùng khác với log vận hành đã giảm thông tin. Không lưu nội dung riêng tư vào log server để làm dashboard.

## 4. Hợp đồng quy tắc

Một rule cần khai báo ID/phiên bản, mục tiêu, phase, capability, loại operation có thể đề xuất, phạm vi đọc/ghi và các điều kiện áp dụng. Detector đọc snapshot; planner trả operation hoặc finding; applier thực hiện operation; validator kiểm tra ràng buộc/kết quả.

**Luật không tự sửa XML khi phân tích, tự mở tệp hệ thống hay tự gọi dịch vụ mạng.** Bộ đăng ký chỉ chứa rule do dự án tin cậy phát hành, không nạp script do người dùng tải lên.

Thứ tự xử lý có chủ đích:

1. Đọc/kiểm tra gói và snapshot nguồn.
2. Đọc style kế thừa, phân tích section, phát hiện vùng bảo vệ.
3. Phân loại vai trò, phân cấp, bìa và nhóm cần duyệt.
4. Resolve profile cùng quyết định, lập kế hoạch.
5. Kiểm tra tiền điều kiện, xung đột và ảnh hưởng dùng chung.
6. Áp dụng lên bản sao nguồn, kiểm tra toàn vẹn.
7. Dựng/đối chiếu trang khi cần; mọi sửa phụ thuộc trang phải thành operation bổ sung được kiểm tra, tối đa số lượt cấu hình.
8. Kiểm tra gói cuối, công bố manifest và kết quả.

**Thứ tự ưu tiên:** ràng buộc bảo toàn/vùng khóa → yêu cầu giữ nguyên của tác giả → quyết định đã duyệt hợp lệ → quy tắc theo mẫu. Người dùng không thể yêu cầu bỏ cổng toàn vẹn. Hai rule ghi cùng một thuộc tính mà không có quan hệ ghi đè được khai báo phải bị phát hiện xung đột; không dùng “rule chạy sau thắng”.

Đặc biệt, không sửa `Normal` hoặc `docDefaults` dùng chung nếu làm thay đổi vùng đã khóa thông qua kế thừa. Một kế hoạch sửa lề có thể ảnh hưởng toàn section dù operation chỉ trỏ vào một node; phải kiểm tra phạm vi ảnh hưởng, không chỉ vị trí ghi.

## 5. Lỗi, một phần và kiểm chứng Word

Phân biệt ba lớp kết quả:

- **Toàn vẹn:** cổng bắt buộc. Thất bại thì không xuất ứng viên.
- **Hoàn thành yêu cầu:** các phép sửa cần thiết có thực hiện được không; nếu bỏ qua có nguyên nhân thì kết quả partial.
- **Hiển thị/tương thích:** PDF có dựng được không, số trang có đối chiếu được không, Word thực tế đã kiểm tra hay chưa.

Renderer không quyết định tính toàn vẹn thay cho validator. PDF không được dựng từ ứng viên chưa vượt kiểm tra tiền dựng. Các operation cập nhật mục lục phải qua kiểm tra lần nữa trước công bố.

Khi thiếu renderer hoặc không suy ra số trang đáng tin, không ghi số 0/phỏng đoán như kết quả đã xác minh. Giữ phần cũ hoặc bỏ qua thao tác tùy chọn nếu có fallback an toàn; báo một phần. Nếu tác vụ bắt buộc không có fallback an toàn thì từ chối tác vụ đó với lý do rõ.

Phiên bản đầu giữ luồng DOCX do bộ OOXML tạo làm kết quả chính; không tự lấy bản DOCX LibreOffice chuyển đổi để thay nguồn. Mở Word, cập nhật field, lưu và mở lại là một lớp nghiệm thu riêng.

## 6. Điểm mở rộng và chi phí thay đổi

| Tính năng | Phần dự kiến thay đổi | Điều kiện/chi phí không được bỏ qua |
|---|---|---|
| Thêm mẫu có các thuộc tính đã hỗ trợ | Profile config + đăng ký + fixture | Kiểm tra giá trị, role styles, UI/defaults, nguồn và phiên bản |
| Thêm một thuộc tính trình bày chưa hỗ trợ | Profile schema + planner/applier/validator | Không thể chỉ thêm JSON; cần backward compatibility |
| Cải tiến nhận diện đề mục | Detector/hierarchy + corpus | Tái đánh giá precision/recall và review groups; quyết định cũ có thể hết hiệu lực |
| Thêm loại sửa | Rule + operation handler + validator + audit mapping | Khai báo ảnh hưởng, xung đột và điều kiện an toàn |
| Đổi bộ dựng PDF | Renderer adapter | Hợp đồng kết quả, phông, hủy, giới hạn, phân trang và Word phải được kiểm chứng lại |
| Nhận văn bản dán | Input adapter và xác nhận nhập | Tạo nguồn sở hữu mới; không hứa giữ bố cục gốc chưa tồn tại |
| Dùng AI gợi ý | Advisor adapter tùy chọn | Chỉ đề xuất; không ghi tài liệu; cần đánh giá chi phí/quyền riêng tư và cổng duyệt |
| Nhiều worker/máy chủ | Queue/store adapters và orchestration | Tệp/trạng thái dùng chung, lock/revision, hủy/TTL/expiry và phân phối lượt chạy |

Không đầu tư trước toàn bộ adapter tương lai. Giữ hợp đồng tối thiểu cho nhu cầu đã chứng minh, rồi mở rộng có kiểm thử.

## 7. API và phiên bản

Giữ các đường Jobs API đang có trong giai đoạn chuyển tiếp. Các ID `hust` và `report` cần alias tương thích; không đổi nghĩa âm thầm. Registry mới phải kiểm tra profile từ tập đăng ký, thay vì chấp nhận chuỗi tùy ý hoặc chỉ sửa frontend.

Metadata mới nên bổ sung theo cách tương thích khi có thể. Trường bắt buộc, đổi nghĩa trạng thái hoặc đổi dạng dữ liệu cần phiên bản schema/API và kế hoạch migration; không chỉ tăng một số version trang trí.

Block/page references thuộc một run; sau xử lý lại không ghép PDF cũ với audit mới. Cache key cần source/profile/rules/decision fingerprint. Renderer version và phông phục vụ giải thích tính tái lập; không thể coi cùng profile là đủ để bảo đảm cùng số trang ở mọi máy.

## 8. Lưu trữ và triển khai

V1 vẫn dùng tệp tạm và JSON; D06 là mô hình khái niệm, không yêu cầu tạo cơ sở dữ liệu quan hệ. Có thể chỉ giữ sản phẩm của run hiện tại để giảm tài nguyên, trong khi metadata cần thiết cho audit vẫn nằm trong TTL. Không mặc nhiên xây lịch sử lưu lâu dài.

Beta hiện tại: Windows chạy DocLint và LibreOffice; Cloudflare Quick Tunnel chuyển tiếp HTTPS về localhost. URL tạm và uptime phụ thuộc máy người vận hành; không phải dịch vụ 24/7. Phiên vẫn tuân thủ TTL kể cả đường hầm còn mở.

Đích máy chủ: HTTPS proxy → một container DocLint → bộ dựng giới hạn và kho tạm riêng. Bảo vệ tài nguyên, IP thật từ proxy đáng tin, phông và cơ chế dọn dữ liệu phải kiểm chứng trên hạ tầng thực. DNS/tên miền không sửa được vấn đề máy chủ tắt.
