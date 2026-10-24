# 04 — Quy trình phát triển và chuyển tiếp

## 1. Quy trình đủ dùng cho nhóm hai người

Không có một danh sách sơ đồ duy nhất bảo đảm dự án không phải thay đổi. Nhóm cần một chuỗi quyết định có truy vết: **vấn đề → mục tiêu → yêu cầu → thiết kế → triển khai → kiểm chứng → phản hồi**. Mỗi sơ đồ chỉ cần tồn tại khi trả lời một câu hỏi cụ thể, và phải được cập nhật khi quyết định liên quan đổi.

| Bước | Sản phẩm đầu ra | Cổng chuyển bước |
|---|---|---|
| 1. Hiểu vấn đề | User story, ví dụ tài liệu, tác động và phạm vi | Biết ai gặp khó khăn, kết quả cần đạt và điều không được đổi |
| 2. Chốt yêu cầu | BP-FR/AC, ưu tiên, ngoại lệ, phép đo | Kiểm tra được bằng bằng chứng; không xung đột INV |
| 3. Thiết kế | Sơ đồ chịu ảnh hưởng, contract/schema, ADR nếu cần | Xác định chủ sở hữu logic, dữ liệu, xung đột và khả năng tương thích |
| 4. Làm mẫu/triển khai nhỏ | Thay đổi hẹp hoặc feature flag khi cần | Có thể so sánh đường cũ/mới; không trộn nhiều refactor và tính năng chưa liên quan |
| 5. Kiểm chứng | Test phù hợp, kiểm tra artifact, bằng chứng UI/Word nếu ảnh hưởng | Đạt AC và hồi quy có nguy cơ; không cần chạy mọi loại test cho chỉnh tài liệu |
| 6. Phát hành beta | Phiên bản, phạm vi, giới hạn, hướng quay lại | Có hướng dẫn và cấu hình tái lập; không quảng cáo vượt bằng chứng |
| 7. Quan sát | Lỗi theo giai đoạn, phản hồi và đo sử dụng | Quay lại bước 1 hoặc chỉnh ưu tiên có căn cứ |

## 2. Mẫu issue trước khi lập trình

```text
Vấn đề và người dùng:
Ví dụ đầu vào / điều kiện tái hiện:
Kết quả mong muốn:
Những gì không được thay đổi:
BP-FR và AC liên quan:
Phần trong / ngoài phạm vi:
Module, contract, schema/API/profile bị ảnh hưởng:
Xung đột rule / vùng dùng chung / dữ liệu riêng tư:
Cách kiểm chứng và môi trường cần thiết:
Cách chuyển tiếp hoặc quay lại khi thất bại:
Người thực hiện / người kiểm tra chéo:
```

Với lỗi đơn giản, chỉ cần các trường có liên quan. Với tính năng thay đổi nội dung được cho phép, cấu trúc lưu trữ hoặc hệ đánh số, cần đầy đủ phân tích tác động.

## 3. Cổng thêm tính năng

Trước khi thêm một tính năng, trả lời lần lượt:

1. Nó có giúp công việc cốt lõi trong 01-PRODUCT không?
2. Nó là thay dữ liệu profile, cải tiến nhận diện, loại operation mới hay thay hạ tầng?
3. Nó có đụng INV, thay đổi ký tự, part dùng chung, schema hoặc quyền truy cập không?
4. Nó nằm ở module nào và phần nào không cần đổi?
5. AC và bằng chứng nào chứng minh đúng, bao gồm phản ví dụ và lỗi?
6. Nếu chưa đủ an toàn, hệ thống bỏ qua, hỏi hay từ chối thế nào?

Ví dụ “thêm mẫu phông mới” chỉ là config nếu engine đã hỗ trợ đủ thuộc tính. “Biến bullet thành đoạn diễn giải” là chức năng viết nội dung, không nhận vào V1. “Chạy nhiều máy chủ” là thay đổi vòng đời dữ liệu và điều phối, không chỉ tăng tham số worker.

## 4. Các ADR đề xuất

| ADR | Quyết định đề xuất | Lý do / hệ quả |
|---|---|---|
| ADR-001 | Modular monolith cho V1 | Nhóm nhỏ, triển khai đơn giản; vẫn cần ranh giới và dependency rõ |
| ADR-002 | Nguồn bất biến, quyết định và run gắn fingerprint | Chạy lại có căn cứ; cần quản lý snapshot/schema và tham chiếu cũ |
| ADR-003 | Planner tách applier; IntegrityGate trước công bố | Kiểm soát tác động và audit; không thay đồng loạt Editor đã ổn định |
| ADR-004 | Profile có version, đơn vị và role styles; backend là nguồn mặc định | Giảm cấu hình trùng và hardcode; profile mới vẫn cần kiểm chứng |
| ADR-005 | Rule có khai báo đọc/ghi, không tự sửa XML khi phân tích | Dễ phát hiện xung đột; loại operation mới cần handler/validator |
| ADR-006 | PDF phụ trợ, Word cần nghiệm thu riêng | Không lấy bản Word chuyển đổi từ renderer thay đầu ra; không coi PDF đúng là Word đúng |
| ADR-007 | Tệp phiên tạm thời, chưa lưu lịch sử dài hạn | Phù hợp beta và quyền riêng tư; nhiều worker cần thiết kế lại adapter vòng đời |

Trạng thái ADR lúc tạo tài liệu: **Proposed**. Sau khi nhóm chốt, ghi người/ngày, lựa chọn khác đã cân nhắc và lý do; khi đổi quyết định dùng ADR thay thế, không xóa lịch sử lý do.

## 5. Kế hoạch chuyển tiếp từ mã hiện tại

### Bước A — Chốt hợp đồng và giữ đường đang chạy

- Mười: rà soát INV, thao tác hiện có và snapshot nguồn; định nghĩa DTO tối thiểu.
- Lương: lập bản đồ luồng UI, mặc định hiện tại và tập tài liệu nghiệm thu.
- Cùng làm: ghi các quyết định Proposed/Accepted và yêu cầu nào còn thiếu bằng chứng.
- Điều kiện xong: chốt phạm vi, có AC mẫu; chưa phải viết lại engine.

### Bước B — Chuẩn hóa profile và mặc định

- Mười: ProfileRegistry/Resolver có version; chuyển từng role style khỏi các nhánh hardcode phù hợp.
- Lương: UI dùng cấu hình hiệu lực và hiển thị nguồn/phạm vi; kiểm tra alias `hust`/`report`.
- Cùng làm: thêm `general` đúng spec đã chốt, kiểm tra Word/PDF và vùng khóa.
- Điều kiện xong: một nguồn defaults, profile mới không làm đổi nghĩa profile cũ âm thầm.

### Bước C — Tách một nhóm rule qua kế hoạch

- Mười: bọc LegacyEngineAdapter; bắt đầu nhóm style thân bài/đề mục rõ, operation và cổng xác minh.
- Lương: kiểm tra nhóm duyệt, audit trước/sau và hai đường cũ/mới trên cùng corpus.
- Cùng làm: khai báo xung đột/vùng ảnh hưởng; chỉ chuyển nhóm đã đủ bằng chứng.
- Điều kiện xong: chưa chuyển các phần mục lục/section phức tạp nếu chưa kiểm chứng.

### Bước D — Minh bạch, tương thích và beta

- Mười: manifest theo run, ranh giới kiểm tra/dựng; ưu tiên vấn đề mục lục Word.
- Lương: giao diện đã sửa/giữ/cần kiểm tra, thử dùng có quan sát và kiểm tra Windows/Word.
- Cùng làm: hồ sơ phát hành, giới hạn, phép đo, danh sách còn tồn tại.
- Điều kiện xong: yêu cầu Must đạt trong phạm vi công bố; tính năng chưa nghiệm thu không được mô tả là đã tương thích hoàn toàn.

Bốn bước này là kế hoạch công việc tiếp theo, không thay lịch sử hay giả định các tuần trong lộ trình 15 tuần đã thực hiện. Mỗi bước có thể chia issue nhỏ; không gắn thời gian ước lượng chắc chắn khi chưa đánh giá khối lượng.

## 6. Checklist rà soát một thay đổi

- Yêu cầu và AC rõ, có người dùng/tình huống cụ thể.
- Logic đúng tầng; không lặp thuật toán giữa UI và backend.
- Rule có điều kiện áp dụng và tác động được khai báo.
- Vùng giữ nguyên, nội dung và đối tượng có kiểm chứng phù hợp.
- Không xuất ứng viên lỗi; status và audit phản ánh việc thực tế.
- Profile/schema/API đổi có version hoặc chuyển tiếp.
- Test thích hợp đạt; thay đổi hiển thị/field có kiểm tra artifact hoặc Word khi cần.
- Sơ đồ/tài liệu liên quan khớp triển khai; không cập nhật sơ đồ không liên quan cho đủ thủ tục.
- Không thêm dữ liệu người dùng vào fixture/Git khi chưa được phép riêng.

## 7. Phân công và ghi nhận

Mười phụ trách chính nghiệp vụ, profile/rules, engine, toàn vẹn và điều phối. Lương phụ trách chính UX, tích hợp, corpus, kiểm thử đầu cuối và tài liệu sử dụng. Hai người kiểm tra chéo các thay đổi ranh giới; vai trò không ngăn người còn lại góp ý hoặc sửa khi cần.

Một thay đổi có thể làm rõ bằng một issue và một sơ đồ nhỏ; mục tiêu của quy trình là giảm quyết định ngầm và giảm lỗi, không tạo thêm giấy tờ không phục vụ phát triển.
