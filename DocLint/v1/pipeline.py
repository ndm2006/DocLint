"""Bounded local workflow, honest partial outcomes, and a final integrity gate."""

from pathlib import Path
import threading
from core.processor import DocumentError
from core.xmlutils import q
from v1.analysis import plain, text_of
from v1.editor import Editor
from v1.renderer import PreviewError, render_pdf, inspect_pdf, font_warnings


def _heading_list(editor):
    heads = {}
    for block in editor.analysis.blocks:
        if (
            block["role"] == "heading"
            and block["certainty"] == "certain"
            and block["position"] > editor.cover_position
        ):
            heads[block["id"]] = block
    heads.update({b["id"]: b for b in editor.heading_blocks})
    return [
        {**b, "text": plain(text_of(editor.analysis.elements[b["id"]]))}
        for b in sorted(heads.values(), key=lambda b: b["position"])
    ]


def page_label(editor, physical_page):
    """Derive the Word counter from explicit section settings, never footer prose."""
    if editor.numbering_applied:
        value = physical_page - int(editor.options.hide_first_page_number)
        return str(value) if value >= 0 else None
    types = [
        section.find(q("pgNumType")) for _, section in editor.analysis.section_nodes
    ]
    first = types[0] if types else None
    fmt = first.get(q("fmt"), "decimal") if first is not None else "decimal"
    if any(
        node is not None
        and (node.get(q("start")) is not None or node.get(q("fmt"), fmt) != fmt)
        for node in types[1:]
    ):
        return None  # Multiple numbering systems/restarts need Word's field engine.
    try:
        start = int(first.get(q("start"), "1")) if first is not None else 1
    except ValueError:
        return None
    value = physical_page + start - 1
    if fmt == "decimal":
        return str(value) if value >= 0 else None
    if fmt in {"lowerRoman", "upperRoman"} and 0 < value < 4000:
        roman = ""
        for integer, letters in [
            (1000, "M"),
            (900, "CM"),
            (500, "D"),
            (400, "CD"),
            (100, "C"),
            (90, "XC"),
            (50, "L"),
            (40, "XL"),
            (10, "X"),
            (9, "IX"),
            (5, "V"),
            (4, "IV"),
            (1, "I"),
        ]:
            count, value = divmod(value, integer)
            roman += letters * count
        return roman.lower() if fmt == "lowerRoman" else roman
    return None


def format_document(
    data, options=None, directory=None, cancel=None, progress=None, preview=True
):
    if directory is None:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="doclint-v1-") as scratch:
            return format_document(data, options, scratch, cancel, progress, preview)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cancel = cancel or threading.Event()
    progress = progress or (lambda stage: None)
    progress("Đang dàn trang theo các lựa chọn đã duyệt")
    editor = Editor(data, options).run()
    heads = _heading_list(editor)
    section_bounds = {}
    for index, (_, section) in enumerate(editor.analysis.section_nodes):
        if editor.analysis.sections[index]["complex"]:
            continue
        margins = section.find(q("pgMar"))
        if margins is not None:
            try:
                section_bounds[index] = tuple(
                    int(margins.get(q(k), str(v))) / 20
                    for k, v in [
                        ("left", 1701),
                        ("right", 1134),
                        ("top", 1134),
                        ("bottom", 1134),
                    ]
                )
            except ValueError:
                pass
    for entry in editor.toc_entries:
        entry["text"] = plain(text_of(editor.analysis.elements[entry["block_id"]]))
    inspection = None
    render_status = {
        "available": False,
        "reason": "Bạn đã tắt bản dựng trong lần xử lý này.",
    }
    toc_status = "not_requested" if not editor.toc_entries else "unresolved"
    stage_warnings = []
    diagnostics = []
    if preview:
        progress("Đang dựng PDF và kiểm tra bố cục theo trang")
        try:
            for iteration in range(3):
                if cancel.is_set():
                    raise DocumentError("Công việc đã bị hủy.")
                output = editor.package.serialize()
                editor.ledger.verify_bytes(output)
                render_pdf(output, directory / "result.pdf", cancel=cancel)
                inspection = inspect_pdf(
                    directory / "result.pdf",
                    heads,
                    editor.analysis.blocks,
                    section_bounds,
                )
                render_status = {
                    "available": True,
                    "page_count": inspection["page_count"],
                    "passes": iteration + 1,
                }
                if not editor.toc_entries:
                    break
                updates = []
                unresolved = []
                for entry in editor.toc_entries:
                    location = inspection["headings"].get(entry["block_id"])
                    if not location:
                        unresolved.append(entry["block_id"])
                        continue
                    label = page_label(editor, location["page"])
                    if label is None:
                        unresolved.append(entry["block_id"])
                        continue
                    if entry["node"].text != label:
                        updates.append((entry, label))
                if not updates:
                    toc_status = "verified" if not unresolved else "partial"
                    break
                if iteration == 2:
                    toc_status = "needs_word_update"
                    break
                for entry, label in updates:
                    editor.ledger.update_generated_text(entry["node"], label)
                    entry["page"] = label
            stage_warnings.extend(inspection["warnings"])
        except PreviewError as exc:
            if exc.diagnostic:
                diagnostics.append(exc.diagnostic)
            render_status = {"available": False, "reason": str(exc)}
            stage_warnings.append(
                {
                    "code": "preview_unavailable",
                    "title": "Chưa kiểm tra được bản dựng",
                    "description": str(exc),
                }
            )
    if editor.toc_entries and toc_status != "verified":
        stage_warnings.append(
            {
                "code": "toc_pages_pending",
                "title": "Mục lục cần cập nhật/kiểm tra trong Word",
                "description": "Chưa đối chiếu ổn định được mọi số trang. Trong Word, chọn mục lục → Update Field. Không coi đây là mục lục đã xác minh hoàn toàn.",
            }
        )
    if render_status["available"]:
        stage_warnings.extend(font_warnings(editor.design.font))
    if cancel.is_set():
        raise DocumentError("Công việc đã bị hủy.")
    progress("Đang đối chiếu toàn vẹn và đóng gói kết quả")
    report = editor.report()
    report["warnings"].extend(stage_warnings)
    report.update(
        version="1.0",
        ai_api=False,
        preview=render_status,
        toc_status=toc_status,
        layout=inspection
        or {"pages": [], "page_count": 0, "headings": {}, "warnings": []},
        options=editor.options.model_dump(),
        diagnostics=diagnostics,
        status="ready"
        if render_status["available"]
        and toc_status in {"not_requested", "verified"}
        and (editor.options.page_numbers == "keep" or editor.numbering_applied)
        else "partial",
    )
    mapped = (inspection or {}).get("block_pages", {})
    report["changed_pages"] = sorted(
        {mapped[c["block_id"]] for c in editor.changes if c.get("block_id") in mapped}
    )
    report["page_mapping_scope"] = (
        "Chỉ đánh dấu thay đổi có đoạn văn định vị duy nhất được trên PDF; không suy đoán các vị trí còn lại."
    )
    report["checks"] = [
        {
            "code": "content",
            "title": "Nội dung và thành phần được bảo vệ",
            "status": "verified",
        },
        {
            "code": "locked",
            "title": "Vùng khóa giữ nguyên",
            "status": "verified",
            "count": len(editor.locked),
        },
        {
            "code": "render",
            "title": "Dựng và đọc bản PDF",
            "status": "verified" if render_status["available"] else "unavailable",
        },
        {
            "code": "headings",
            "title": "Định vị tiêu đề trên trang",
            "status": "verified"
            if inspection and len(inspection["headings"]) == len(heads)
            else "partial",
            "matched": len(inspection["headings"]) if inspection else 0,
            "total": len(heads),
        },
        {"code": "toc", "title": "Số trang trong mục lục", "status": toc_status},
        {
            "code": "numbering",
            "title": "Áp dụng số trang",
            "status": "not_requested"
            if editor.options.page_numbers == "keep"
            else "verified"
            if editor.numbering_applied
            else "partial",
        },
    ]
    output = editor.package.serialize()
    editor.ledger.verify_bytes(output)
    temporary = directory / "result.pending.docx"
    temporary.write_bytes(output)
    temporary.replace(directory / "result.docx")
    return output, report
