# Thư viện và giấy phép bên thứ ba

DocLint không gọi API AI thương mại. Miễn phí API không loại bỏ nghĩa vụ giấy phép hoặc chi phí máy chủ.

- FastAPI, python-docx: MIT.
- Starlette, Uvicorn, lxml: BSD-3-Clause (các thư viện native đi kèm có giấy phép riêng).
- Pillow: MIT-CMU.
- pypdfium2: `(Apache-2.0 OR BSD-3-Clause) AND LicenseRef-PdfiumThirdParty`. PDFium và các thành phần native có bộ thông báo/giấy phép kèm bản phân phối; giữ các tệp license của package khi đóng gói.
- LibreOffice: bộ giấy phép của LibreOffice, gồm MPL-2.0 và giấy phép thành phần đi kèm. Cài từ nguồn chính thức hoặc kho hệ điều hành; không loại bỏ notices.
- Liberation/Carlito: phông mở theo SIL Open Font License; giữ license của gói phông khi phân phối.
- Times New Roman/Calibri: không được coi là phông mở. DocLint không đóng gói chúng; người dùng/máy chủ phải có quyền sử dụng hợp lệ hoặc dùng phông thay thế và nhận cảnh báo.
- Playwright và Ruff chỉ là công cụ phát triển/kiểm thử; xem giấy phép trong các package tương ứng.

Bản thân dự án chưa được gán giấy phép nguồn mở mới trong thay đổi này; quyền cấp phép mã dự án thuộc chủ repository. Danh sách này không thay thế toàn bộ các thông báo giấy phép đi kèm dependency.
