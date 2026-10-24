# Các sơ đồ DocLint — dự thảo thiết kế 0.1

Các hình dưới đây dùng các góc nhìn khác nhau; không có một sơ đồ duy nhất thay thế SRS, kiểm thử và quyết định sản phẩm. Đọc cùng [định hướng](01-PRODUCT.md), [yêu cầu](02-REQUIREMENTS.md) và [kiến trúc](03-ARCHITECTURE.md).

Mở hình SVG để phóng to. Mã Mermaid chỉnh sửa được nằm trong thư mục `diagrams`. Thiết kế đích và hiện trạng được phân biệt ở mô tả từng hình.

## D01. Bối cảnh hệ thống

Xác định ai sử dụng và sản phẩm trao đổi thông tin gì với bên ngoài. Bộ dựng và hàng đợi là chi tiết bên trong, không được coi như người dùng nghiệp vụ.

![Bối cảnh hệ thống](rendered/D01-context.svg)

[Mở hình SVG](rendered/D01-context.svg) · [Mã nguồn sơ đồ](diagrams/D01-context.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
flowchart LR
    Author["Tác giả báo cáo<br/>Có nội dung, cần hoàn thiện hình thức"]
    Operator["Người vận hành<br/>Theo dõi môi trường và lỗi"]
    DocLint["DocLint<br/>Phân tích, đề xuất, dàn trang và kiểm chứng"]
    Reader["Ứng dụng đọc DOCX/PDF<br/>Microsoft Word và trình đọc PDF"]
    Author -->|"DOCX, mẫu và lựa chọn"| DocLint
    DocLint -->|"Nhóm cần duyệt, tiến độ, thay đổi, cảnh báo"| Author
    DocLint -->|"Tệp kết quả hợp lệ trong hạn phiên"| Author
    Author -->|"Mở và kiểm tra tệp đã tải"| Reader
    Operator -->|"Cấu hình, kiểm tra năng lực, xử lý lỗi"| DocLint
    DocLint -->|"Trạng thái kỹ thuật giảm thông tin"| Operator
```

</details>

## D02. Các ca sử dụng

Biểu diễn mục tiêu tác nhân bằng flowchart Mermaid; đường liên kết không thể hiện thứ tự thực hiện. Đây là mô hình ca sử dụng, không phải bản UML dùng đầy đủ ký pháp actor/include/extend.

![Các ca sử dụng](rendered/D02-use-cases.svg)

[Mở hình SVG](rendered/D02-use-cases.svg) · [Mã nguồn sơ đồ](diagrams/D02-use-cases.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
flowchart LR
    A(("Tác giả"))
    O(("Người vận hành"))
    subgraph S["Ranh giới DocLint — mô hình ca sử dụng"]
        U1(["UC-01 Tải và kiểm tra DOCX"])
        U2(["UC-02 Xem phân tích, duyệt nhóm chưa chắc chắn"])
        U3(["UC-03 Chọn mẫu và dàn trang"])
        U4(["UC-04 Xem thay đổi, phần giữ và cảnh báo"])
        U5(["UC-05 Tải sản phẩm đã kiểm chứng"])
        U6(["UC-06 Đổi lựa chọn, chạy lại từ nguồn"])
        U7(["UC-07 Hủy hoặc xóa phiên"])
        U8(["UC-08 Kiểm tra năng lực và chẩn đoán"])
    end
    A --- U1
    A --- U2
    A --- U3
    A --- U4
    A --- U5
    A --- U6
    A --- U7
    O --- U8
```

</details>

## D03. Luồng hoạt động nghiệp vụ

Các nhánh kiểm tra đầu vào, duyệt, lập kế hoạch, sửa và công bố. Kế hoạch có thể không có operation nếu chỉ bảo tồn. Việc giữ nguyên toàn tệp vẫn cần kiểm chứng và giải thích phạm vi.

![Luồng hoạt động nghiệp vụ](rendered/D03-activity.svg)

[Mở hình SVG](rendered/D03-activity.svg) · [Mã nguồn sơ đồ](diagrams/D03-activity.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
flowchart TD
    A(["Nhận DOCX"]) --> B{"Đầu vào hợp lệ<br/>và trong giới hạn?"}
    B -->|"Không"| Reject["Từ chối, giải thích lỗi"]
    B -->|"Có"| C["Lưu nguồn bất biến<br/>Phân tích vai trò và vùng bảo vệ"]
    C --> D{"Có nhóm cần xác nhận?"}
    D -->|"Có"| Review["Gom nhóm: giữ nguyên / thân bài / đề mục<br/>Nhận lựa chọn có căn cứ"]
    D -->|"Không"| Profile["Phân giải mẫu và cấu hình hiệu lực"]
    Review --> Current{"Lựa chọn còn khớp<br/>nguồn và phân tích?"}
    Current -->|"Không"| C
    Current -->|"Có"| Profile
    Profile --> Plan["Lập kế hoạch<br/>Tự sửa phần rõ; bỏ qua phần rủi ro"]
    Plan --> Eligible{"Tiền điều kiện và<br/>xung đột hợp lệ?"}
    Eligible -->|"Không"| Hold["Chặn thao tác xung đột<br/>Yêu cầu điều chỉnh hoặc giữ nguyên"]
    Eligible -->|"Có"| Apply["Áp dụng lên bản sao nguồn<br/>Ghi thao tác thực tế"]
    Apply --> Gate1{"Toàn vẹn sau sửa đạt?"}
    Gate1 -->|"Không"| Stop["Chặn ứng viên<br/>Không cho tải bản lỗi"]
    Gate1 -->|"Có"| Need{"Cần bản dựng / đối chiếu trang?"}
    Need -->|"Không"| Gate2
    Need -->|"Có"| Render["Dựng và đọc PDF có giới hạn"]
    Render --> Available{"Có đủ dữ kiện trang?"}
    Available -->|"Không"| Partial["Ghi phần chưa kiểm chứng<br/>Dùng fallback an toàn, không đoán số"]
    Available -->|"Có"| Finalize["Hoàn thiện phần phụ thuộc trang<br/>qua operation bổ sung được phép"]
    Finalize --> Gate2{"Gói cuối vượt<br/>cổng toàn vẹn?"}
    Partial --> Gate2
    Gate2 -->|"Không"| Stop
    Gate2 -->|"Có"| Publish["Công bố đúng run/revision<br/>ready hoặc partial; giải thích phạm vi"]
    Publish --> Z(["Xem, tải hoặc chạy lại từ nguồn"])
```

</details>

## D04. Thành phần và hướng phụ thuộc

Kiến trúc đích đề xuất. Mũi tên liền biểu diễn phụ thuộc/sử dụng; nét đứt biểu diễn adapter hiện thực cổng. Không khẳng định mọi module đích đã có lớp hiện thực trong mã hiện tại.

![Thành phần và hướng phụ thuộc](rendered/D04-components.svg)

[Mở hình SVG](rendered/D04-components.svg) · [Mã nguồn sơ đồ](diagrams/D04-components.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
flowchart TB
    UI["Giao diện web<br/>Nhóm duyệt và kết quả dễ hiểu"]
    API["API / DTO<br/>Xác thực yêu cầu và phiên bản"]
    Jobs["JobService<br/>Revision, hàng đợi, hủy và TTL"]
    Workflow["FormatService<br/>Điều phối ca sử dụng"]
    subgraph Domain["Nghiệp vụ tài liệu — hợp đồng đích đề xuất"]
        Analyze["Analyzer<br/>Vai trò, phân cấp, bìa và evidence"]
        Profiles["ProfileResolver<br/>Mẫu có phiên bản, role styles và defaults"]
        Planner["Planner / RuleRegistry<br/>Đề xuất operation, không tự ghi XML"]
        Guard["ProtectionPolicy / PlanValidator<br/>Vùng ảnh hưởng, tiền điều kiện, xung đột"]
        Gate["IntegrityGate<br/>Nguồn, phần gói, đối tượng và vùng khóa"]
        Audit["AuditProjection<br/>Đã sửa / giữ nguyên / cần kiểm tra"]
    end
    subgraph Ports["Cổng do nghiệp vụ/ứng dụng định nghĩa"]
        Reader["DocumentReader"]
        Writer["DocumentApplier"]
        Preview["PreviewRenderer / PageInspector"]
        Store["JobStore / ArtifactStore"]
    end
    subgraph Adapters["Adapter hiện thực cổng"]
        OOXML["Đọc/ghi gói OOXML<br/>LegacyEngineAdapter trong chuyển tiếp"]
        Office["LibreOffice + PDFium"]
        Files["Tệp tạm + JSON + đồng hồ"]
    end
    UI --> API --> Jobs --> Workflow
    Workflow --> Analyze
    Workflow --> Profiles
    Workflow --> Planner
    Planner --> Guard
    Workflow --> Gate
    Workflow --> Audit
    Analyze --> Reader
    Workflow --> Writer
    Workflow --> Preview
    Jobs --> Store
    Workflow --> Store
    OOXML -.->|"hiện thực"| Reader
    OOXML -.->|"hiện thực"| Writer
    Office -.->|"hiện thực"| Preview
    Files -.->|"hiện thực"| Store
```

</details>

## D05. Trình tự dàn trang và công bố

Minh họa hợp đồng đích của một lượt xử lý, gồm nhận bất đồng bộ và cổng kiểm chứng. Luật hủy/TTL và các lỗi khác phải đọc cùng D07, không suy ra rằng sơ đồ đã liệt kê mọi ngoại lệ.

![Trình tự dàn trang và công bố](rendered/D05-sequence.svg)

[Mở hình SVG](rendered/D05-sequence.svg) · [Mã nguồn sơ đồ](diagrams/D05-sequence.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
sequenceDiagram
    actor User as Tác giả
    participant API as Web API
    participant Jobs as JobService
    participant Flow as FormatService
    participant Plan as Planner và Guard
    participant Apply as OOXML Applier
    participant Gate as IntegrityGate
    participant Render as Bộ dựng PDF
    participant Store as Kho phiên và sản phẩm
    User->>API: Dàn trang với lựa chọn và revision
    API->>Jobs: Kiểm tra phiên, lựa chọn và trạng thái
    alt Đã hết hạn hoặc yêu cầu cũ/xung đột
        Jobs-->>API: Từ chối có lý do
        API-->>User: Không chạy với dữ liệu sai
    else Được tiếp nhận
        Jobs->>Store: Gắn revision/run và xếp hàng
        API-->>User: 202 và địa chỉ theo dõi
        Jobs->>Flow: Bắt đầu run khi có lượt
        Flow->>Store: Đọc bản gốc và snapshot đã gắn phiên bản
        Flow->>Plan: Resolve profile, lập và kiểm tra kế hoạch
        Plan-->>Flow: Operation hợp lệ và phần bỏ qua
        Flow->>Apply: Áp dụng lên bản sao nguồn
        Apply-->>Flow: Ứng viên và thao tác thực tế
        Flow->>Gate: Kiểm tra trước dựng
        alt Vi phạm toàn vẹn
            Gate-->>Flow: Từ chối ứng viên
            Flow->>Store: Ghi failed, không công bố sản phẩm lỗi
        else Ứng viên hợp lệ
            opt Cần dựng hoặc đối chiếu trang
                Flow->>Render: Dựng/đọc PDF với timeout và hủy
                Render-->>Flow: Dữ kiện trang hoặc lỗi có kiểm soát
                Note over Flow,Gate: Sửa phụ thuộc trang phải thành operation bổ sung hợp lệ, không đoán số
            end
            Flow->>Gate: Kiểm tra gói cuối và thao tác bổ sung
            alt Cổng cuối đạt và run còn hiệu lực
                Flow->>Store: Công bố nguyên tử manifest, checks, audit với ready/partial
            else Cổng cuối lỗi hoặc đã hủy/hết hạn
                Flow->>Store: Không công bố, xử lý lỗi/dọn theo vòng đời
            end
        end
        User->>API: Theo dõi và tải kết quả
        API->>Store: Kiểm tra TTL, run hiện tại và manifest đã duyệt
        Store-->>API: Sản phẩm được phép hoặc lý do từ chối
        API-->>User: DOCX/PDF khi có, thay đổi và cảnh báo
    end
```

</details>

## D06. Mô hình dữ liệu khái niệm

Các quan hệ thuộc phiên tạm thời. Có thể hiện thực bằng JSON/tệp; không yêu cầu tạo các bảng SQL. ID khối nằm trong AnalysisSnapshot, không được coi là định danh vĩnh viễn.

![Mô hình dữ liệu khái niệm](rendered/D06-data-model.svg)

[Mở hình SVG](rendered/D06-data-model.svg) · [Mã nguồn sơ đồ](diagrams/D06-data-model.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
erDiagram
    JOB ||--|| SOURCE : owns
    JOB ||--o{ RUN : contains
    SOURCE ||--o{ ANALYSIS : analyzed_as
    ANALYSIS ||--o{ DECISIONS : reviewed_with
    ANALYSIS ||--o{ PLAN : basis_for
    DECISIONS ||--o{ PLAN : supplies
    PROFILE ||--o{ PLAN : resolves_to
    PLAN ||--o{ OPERATION : contains
    PLAN ||--o{ RUN : executed_as
    RUN ||--o{ CHECK : verified_by
    RUN ||--o{ AUDIT_EVENT : explained_by
    RUN ||--o{ ARTIFACT : produces
    JOB {
        string id
        datetime received_at
        datetime expires_at
        string status
        int revision
    }
    SOURCE {
        string source_id
        string sha256
        string original_ref
    }
    ANALYSIS {
        string analysis_id
        string schema_version
        string analyzer_version
        string source_sha256
        json blocks_regions_evidence
    }
    DECISIONS {
        string decision_id
        string analysis_id
        int revision
        json choices_and_locks
    }
    PROFILE {
        string profile_id
        string version
        string effective_hash
    }
    PLAN {
        string plan_id
        string fingerprint
        string ruleset_version
        string engine_version
    }
    OPERATION {
        string operation_id
        string rule_id_version
        string target_ref
        json preconditions_and_payload
    }
    RUN {
        string run_id
        int job_revision
        string state
        string environment_fingerprint
    }
    CHECK {
        string code
        string result
        string scope
    }
    AUDIT_EVENT {
        string event_id
        string event_type
        string target_ref
        json reason_before_after
    }
    ARTIFACT {
        string artifact_id
        string run_id
        string mime_sha256
        boolean publishable
    }
```

</details>

## D07. Vòng đời phiên và trạng thái

Các trạng thái vận hành dựa trên V1; hết hạn logic được tách khỏi thời điểm dọn vật lý. Ready/partial đều phải qua cổng toàn vẹn trước tải, và partial không có nghĩa mọi yêu cầu đã được làm.

![Vòng đời phiên và trạng thái](rendered/D07-job-lifecycle.svg)

[Mở hình SVG](rendered/D07-job-lifecycle.svg) · [Mã nguồn sơ đồ](diagrams/D07-job-lifecycle.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
stateDiagram-v2
    state "Phiên còn hiệu lực" as Live {
        [*] --> queued
        queued --> analyzing: action analyze
        analyzing --> review: Phân tích xong
        review --> queued: Duyệt và gửi format
        queued --> formatting: action format
        formatting --> ready: Đạt yêu cầu và các cổng bắt buộc
        formatting --> partial: Toàn vẹn đạt, có phần bỏ qua/chưa kiểm chứng
        analyzing --> failed: Lỗi không thể tiếp tục
        formatting --> failed: Lỗi hoặc vi phạm cổng
        ready --> queued: Đổi lựa chọn, chạy lại từ nguồn
        partial --> queued: Đổi lựa chọn, chạy lại từ nguồn
    }
    [*] --> Live: DOCX hợp lệ, tạo phiên
    Live --> deleting: Người dùng yêu cầu hủy/xóa
    Live --> Inaccessible: Hết TTL, chặn truy cập
    state "Hết hạn logic — không phải field trạng thái bắt buộc" as Inaccessible
    Inaccessible --> deleting: Bộ dọn đang chạy hoặc khi khởi động lại
    deleting --> [*]: Đã dừng tác vụ và hoàn tất dọn
    note right of formatting
        Giai đoạn kiểm tra/dựng nằm trong progress.
        Không coi mọi giai đoạn là trạng thái API mới.
    end note
    note right of partial
        Có thể gồm chỉ bảo tồn toàn tệp.
        Không đồng nghĩa đã sửa mọi yêu cầu.
    end note
```

</details>

## D08. Triển khai beta và phương án máy chủ

Beta Windows/Quick Tunnel là cách đang hướng dẫn sử dụng. Phần máy chủ là phương án đích, không phải dịch vụ 24/7 đã triển khai. Không cần chạy đồng thời cả hai nhánh.

![Triển khai beta và phương án máy chủ](rendered/D08-deployment.svg)

[Mở hình SVG](rendered/D08-deployment.svg) · [Mã nguồn sơ đồ](diagrams/D08-deployment.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
flowchart TB
    Browser["Trình duyệt người dùng"]
    subgraph Beta["Beta hiện tại — máy Windows phải tiếp tục chạy"]
        Tunnel["Cloudflare Quick Tunnel<br/>HTTPS và địa chỉ tạm"]
        Agent["cloudflared trên Windows"]
        WinApp["DocLint FastAPI<br/>localhost:8000, một hàng đợi"]
        WinOffice["LibreOffice cục bộ<br/>Bản sao dựng tạm"]
        WinFiles[("Kho phiên tạm<br/>Nguồn, phân tích, sản phẩm và TTL")]
        Tunnel --> Agent --> WinApp
        WinApp --> WinOffice
        WinApp --> WinFiles
    end
    subgraph Target["Đích máy chủ — phương án triển khai sau"]
        Proxy["HTTPS proxy<br/>IP thật chỉ từ proxy đáng tin"]
        subgraph Box["Container giới hạn quyền và tài nguyên"]
            Server["DocLint API + một worker<br/>Chưa tự tăng nhiều bản chạy"]
            LocalOffice["Bộ dựng Office giới hạn<br/>Hủy và timeout"]
            Scratch[("Kho tạm riêng<br/>Không sao lưu tài liệu người dùng")]
            Server --> LocalOffice
            Server --> Scratch
        end
        Proxy --> Server
    end
    Browser -->|"HTTPS beta"| Tunnel
    Browser -.->|"HTTPS khi đã triển khai máy chủ"| Proxy
```

</details>

## D09. Vòng lặp phát triển và kiểm chứng

Một thay đổi đi từ vấn đề/AC đến bằng chứng và phản hồi. Thiết kế được cập nhật khi bị ảnh hưởng; không yêu cầu viết lại mọi tài liệu cho một thay đổi nhỏ.

![Vòng lặp phát triển và kiểm chứng](rendered/D09-development-process.svg)

[Mở hình SVG](rendered/D09-development-process.svg) · [Mã nguồn sơ đồ](diagrams/D09-development-process.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
flowchart TD
    A["Vấn đề và ví dụ tái hiện"] --> B["Yêu cầu, phạm vi, AC và INV"]
    B --> C{"Dùng được hợp đồng hiện có?"}
    C -->|"Có"| E["Thực hiện thay đổi nhỏ"]
    C -->|"Không"| D["Phân tích tác động<br/>ADR, schema và chuyển tiếp"]
    D --> E
    E --> F["Kiểm chứng phù hợp<br/>Nghiệp vụ, hồi quy, artifact/Word khi cần"]
    F --> G{"Đạt AC và cổng chất lượng?"}
    G -->|"Không"| E
    G -->|"Có"| H["Rà soát chéo<br/>Cập nhật tài liệu chịu ảnh hưởng"]
    H --> I["Phát hành beta có phiên bản<br/>Phạm vi, giới hạn, cách quay lại"]
    I --> J["Quan sát lỗi và đo thử dùng"]
    J --> A
```

</details>

## D10. Luồng dữ liệu phân rã

Mô hình DFD mức phân rã đầu tiên theo tiến trình P1–P6; kho D1–D5 là kho logic. D3 chứa ứng viên chưa công bố, không phải đường tải công khai. D05 mô tả thứ tự/cổng trước dựng và sau dựng chi tiết hơn.

![Luồng dữ liệu phân rã](rendered/D10-data-flow.svg)

[Mở hình SVG](rendered/D10-data-flow.svg) · [Mã nguồn sơ đồ](diagrams/D10-data-flow.mmd)

<details>
<summary>Xem bản Mermaid</summary>

```mermaid
flowchart TB
    User["Tác giả"]
    P1(["P1 Tiếp nhận và kiểm tra"])
    P2(["P2 Phân tích và bảo vệ"])
    P3(["P3 Phân giải quyết định và lập kế hoạch"])
    P4(["P4 Áp dụng thay đổi và dựng có điều kiện"])
    P5(["P5 Đối chiếu và quyết định công bố"])
    P6(["P6 Cung cấp kết quả trong hạn phiên"])
    D1[("D1 Nguồn bất biến")]
    D2[("D2 Phân tích, quyết định, kế hoạch theo phiên")]
    D3[("D3 Ứng viên và dữ liệu dựng chưa công bố")]
    D4[("D4 Profile và ruleset có phiên bản")]
    D5[("D5 Manifest, checks, audit và sản phẩm hợp lệ")]
    User -->|"DOCX"| P1
    P1 -->|"Nguồn hợp lệ"| D1
    D1 -->|"Gói nguồn"| P2
    P2 -->|"Snapshot, vùng khóa và nhóm duyệt"| D2
    P2 -->|"Nhóm cần xác nhận"| User
    User -->|"Lựa chọn và revision"| P3
    D2 -->|"Snapshot"| P3
    D4 -->|"Cấu hình đã phân giải"| P3
    P3 -->|"Kế hoạch hợp lệ và phần bỏ qua"| D2
    D2 -->|"Kế hoạch và khóa"| P4
    D1 -->|"Nguồn cho lần chạy"| P4
    P4 -->|"Ứng viên, thao tác thực tế, dữ kiện trang"| D3
    D1 -->|"Nguồn đối chiếu"| P5
    D2 -->|"Phạm vi được phép"| P5
    D3 -->|"Ứng viên cuối"| P5
    P5 -->|"Đạt cổng: manifest và sản phẩm"| D5
    P5 -->|"Không đạt: trạng thái lỗi, không có bản lỗi được phép tải"| P6
    D5 -->|"Kết quả đúng run"| P6
    User -->|"Yêu cầu xem/tải"| P6
    P6 -->|"Tệp được phép, thay đổi, cảnh báo hoặc lỗi"| User
```

</details>
