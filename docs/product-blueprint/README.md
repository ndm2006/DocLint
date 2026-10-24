# DocLint — Định hướng và thiết kế phát triển

**Bản dự thảo 0.1 · 24/10/2026 · dùng để cùng thống nhất trước khi thay đổi kiến trúc.**

> Giúp người đã có nội dung báo cáo chuyển một bản DOCX thiếu nhất quán thành tài liệu dễ đọc, bằng các thay đổi bố cục có kiểm soát, có giải thích và có kiểm chứng bảo toàn.

Tình huống trọng tâm là báo cáo tiếng Việt một cột, được sao chép từ AI hoặc ghép từ nhiều thành viên. V1 xử lý DOCX có sẵn; ô dán văn bản trực tiếp là hướng mở rộng sau. Nhóm không đặt mục tiêu viết lại nội dung, làm thay công việc chuyên môn hoặc xử lý mọi thiết kế Word.

Tài liệu này phân biệt **hiện trạng mã nguồn** với **thiết kế đích đề xuất**. Việc thêm tài liệu không đồng nghĩa bộ lập kế hoạch, registry quy tắc hoặc giao diện nhật ký mới đã được triển khai. Các quyết định đề xuất cần được nhóm chốt trước khi lập trình tương ứng.

**Bản đọc/tải:** [PDF tổng hợp](DocLint_Product_Blueprint_v0.1.pdf) · [HTML đọc ngoại tuyến](DocLint_Product_Blueprint_v0.1.html) · [ZIP gồm tài liệu và mã sơ đồ](DocLint_Product_Blueprint_v0.1.zip). Các sơ đồ vector có thể phóng to; ưu tiên SVG khi cần xem chi tiết.

## Cách đọc

| Tài liệu | Câu hỏi được giải quyết |
|---|---|
| [01 — Sản phẩm và phạm vi](01-PRODUCT.md) | Giải quyết việc gì, cho ai, giới hạn đến đâu? |
| [02 — Yêu cầu và nghiệm thu](02-REQUIREMENTS.md) | Làm thế nào biết chức năng đúng và an toàn? |
| [03 — Kiến trúc và hợp đồng mở rộng](03-ARCHITECTURE.md) | Tính năng nằm ở đâu, được phép thay đổi gì? |
| [04 — Quy trình phát triển và chuyển tiếp](04-DEVELOPMENT.md) | Thêm tính năng thế nào để hạn chế ảnh hưởng phần đã ổn định? |
| [Các sơ đồ](DIAGRAMS.md) | Toàn bộ hình biểu diễn và ý nghĩa từng sơ đồ |

## Những quyết định đề xuất quan trọng nhất

1. Một quy trình chính: **tải DOCX → phân tích → xác nhận phần chưa chắc chắn → dàn trang → kiểm chứng → xem và tải kết quả**.
2. Một mẫu mặc định có phiên bản: **Báo cáo phổ thông DocLint**, không gắn chứng nhận của tổ chức bên ngoài khi chưa đối chiếu đúng nguồn.
3. Ba hướng quyết định: **tự sửa / cần xác nhận / giữ nguyên**. Không hỏi lại mọi đoạn.
4. Bản gốc bất biến trong phiên; mỗi lần xử lý lại bắt đầu từ bản gốc.
5. Quy tắc đề xuất thay đổi; bộ áp dụng OOXML là nơi duy nhất thực hiện thay đổi; bộ kiểm tra là cổng trước khi công bố.
6. Giải thích bằng thay đổi thực tế: **ở đâu, trước/sau, lý do, đã áp dụng hay bỏ qua, kết quả kiểm tra**.
7. Giữ kiến trúc ứng dụng nguyên khối có phân mô-đun; một tiến trình và một hàng đợi xử lý trong beta hiện tại.
8. Mở rộng từng bước bằng hợp đồng có phiên bản, kiểm thử và chuyển tiếp tương thích. Không cam kết rằng thêm tính năng sẽ không bao giờ cần sửa mã hoặc mô hình dữ liệu.

## Bộ sơ đồ

| Mã | Sơ đồ | Góc nhìn |
|---|---|---|
| D01 | Bối cảnh hệ thống | Người dùng và ranh giới sản phẩm |
| D02 | Ca sử dụng | Mục tiêu của tác giả và người vận hành |
| D03 | Hoạt động nghiệp vụ | Nhánh sửa, xác nhận, giữ nguyên và kiểm chứng |
| D04 | Thành phần và phụ thuộc | Kiến trúc đích đề xuất |
| D05 | Tuần tự dàn trang | Hợp đồng giữa các thành phần |
| D06 | Mô hình dữ liệu khái niệm | Bản gốc, phân tích, quyết định, kế hoạch, lần chạy và sản phẩm |
| D07 | Vòng đời phiên | Trạng thái, xử lý lại, hết hạn và xóa |
| D08 | Triển khai beta và máy chủ | Đường đi thực của yêu cầu và giới hạn vận hành |
| D09 | Vòng lặp phát triển | Yêu cầu → thiết kế → mã → bằng chứng → phát hành |
| D10 | Luồng dữ liệu phân rã | Tiến trình nào đọc/ghi loại dữ liệu nào |

Các tệp `.mmd` chỉnh sửa được nằm trong [diagrams](diagrams). Bản vẽ là công cụ kiểm tra quyết định thiết kế, không phải chứng nhận hệ thống đã có đủ tính năng.

## Bằng chứng và hiện trạng

Đối chiếu nền mã `67750e84773308b38c67776809010f50db9c47bc`. Các lần chạy 155 ca kiểm thử đã được ghi trong báo cáo trước đây; chúng không được chạy lại chỉ vì thay đổi tài liệu này và không chứng minh những hợp đồng mới đã được triển khai. Kiểm chứng cập nhật mục lục bằng Microsoft Word thực tế vẫn là hạng mục ưu tiên.

Tài liệu liên quan: [phạm vi V1 đang có](../V1_SCOPE.md), [bảo vệ bố cục chọn lọc](../SELECTIVE_LAYOUT.md), [hồ sơ kiểm chứng](../VALIDATION.md).
