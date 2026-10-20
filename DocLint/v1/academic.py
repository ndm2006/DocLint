"""Section-aware academic numbering without rewriting report content."""

from copy import deepcopy
import re
from lxml import etree
from core.xmlutils import NS, q
from v1.design import attrs, ensure
from v1.fields import (
    _ends_page,
    _flow_before,
    _resolve_part,
    _safe_footer,
    add_page_numbers,
)
from v1.package import R
from v1.analysis import folded, on


def _boundary(editor, target, template, kind):
    body = editor.analysis.body
    previous = _flow_before(target)
    previous_id = next(
        (bid for bid, n in editor.analysis.elements.items() if n is previous), None
    )
    if (
        previous is not None
        and previous_id not in editor.locked
        and _ends_page(previous)
    ):
        breaks = previous.xpath('.//w:br[@w:type="page"]', namespaces=NS)
        if breaks:
            editor.ledger.consume_page_break(breaks[-1])
    section = deepcopy(template)
    attrs(
        section,
        "type",
        {
            "val": "continuous"
            if previous_id in editor.locked and _ends_page(previous)
            else "nextPage"
        },
    )
    attrs(section, "titlePg", {"val": 0})
    attrs(section, "vAlign", {"val": "top"})
    old_border = section.find(q("pgBorders"))
    if old_border is not None:
        section.remove(old_border)
    if kind == "cover" and editor.options.cover == "academic":
        attrs(section, "vAlign", {"val": "center"})
        border = attrs(
            section, "pgBorders", {"offsetFrom": "page", "display": "firstPage"}
        )
        for side in ("top", "left", "bottom", "right"):
            attrs(
                border,
                side,
                {"val": "single", "sz": 8, "space": 24, "color": editor.design.accent},
            )
    marker = etree.Element(q("p"))
    pp = ensure(marker, "pPr")
    attrs(pp, "spacing", {"before": 0, "after": 0, "line": 20, "lineRule": "exact"})
    pp.append(section)
    editor.ledger.append_generated(
        body, marker, "academic_section", list(body).index(target)
    )
    first = target if target.tag == q("p") else target.find(".//" + q("p"))
    first_id = next(
        (bid for bid, n in editor.analysis.elements.items() if n is first), None
    )
    if first is not None and first_id not in editor.locked:
        editor.prop(ensure(first, "pPr"), "pageBreakBefore", {"val": 0})
    return section


def academic_sections(editor):
    analysis = editor.analysis
    cover_section = (
        analysis.section_nodes[0][1]
        if len(analysis.section_nodes) == 2
        and analysis.section_nodes[0][0] == editor.cover_position
        else None
    )
    if (
        (len(analysis.section_nodes) != 1 and cover_section is None)
        or any(s["complex"] for s in analysis.sections)
        or editor.options.locked_blocks
    ):
        editor.warn(
            "academic_sections_preserved",
            "Giữ hệ thống section hiện có",
            "Số trang học thuật tự động áp dụng cho báo cáo một section dọc không có vùng khóa thủ công; bố cục nhiều section được giữ và cần kiểm tra riêng.",
        )
        return
    if "word/settings.xml" in editor.package.parts and on(
        editor.package.xml("word/settings.xml").find(q("evenAndOddHeaders"))
    ):
        editor.warn(
            "numbering_preserved",
            "Giữ số trang gốc",
            "Tài liệu có header/footer chẵn lẻ riêng; không tách thêm section đánh số học thuật.",
        )
        return
    relations = (
        editor.package.xml("word/_rels/document.xml.rels")
        if "word/_rels/document.xml.rels" in editor.package.parts
        else []
    )
    targets = {
        r.get("Id"): r.get("Target")
        for r in relations
        if r.get("TargetMode") != "External"
    }
    template = analysis.section_nodes[-1][1]
    for ref in template.findall(q("footerReference")):
        try:
            name = _resolve_part(
                "word/document.xml", targets.get(ref.get(f"{{{R}}}id"))
            )
            if name not in editor.package.parts or not _safe_footer(
                editor.package.xml(name)
            ):
                raise ValueError()
        except ValueError:
            editor.warn(
                "numbering_preserved",
                "Giữ số trang gốc",
                "Footer có cấu trúc chưa hỗ trợ tách số trang học thuật.",
            )
            return
    body = analysis.body
    front = [
        n for n in getattr(editor, "frontmatter_nodes", []) if n.getparent() is body
    ]
    if editor.generated_toc is not None and editor.generated_toc.getparent() is body:
        front.insert(0, editor.generated_toc)
    elif analysis.toc_nodes:
        front = [n for n in analysis.toc_nodes if n.getparent() is body] + front
    front = sorted(set(front), key=lambda n: list(body).index(n))
    excluded = set(front) | set(analysis.toc_nodes)
    candidates = [
        b
        for b in analysis.blocks
        if b["position"] > editor.cover_position
        and analysis.elements[b["id"]].getparent() is body
        and analysis.elements[b["id"]] not in excluded
        and (b["text"] or b["role"] in {"image", "table"})
    ]
    if not candidates:
        editor.warn(
            "academic_body_missing",
            "Chưa xác định phần thân bài",
            "Giữ số trang gốc vì không có điểm bắt đầu thân bài an toàn.",
        )
        return
    first_body = candidates[0]
    front_intro = bool(
        re.match(
            r"^(tom tat|loi mo dau|loi noi dau|loi cam on|abstract|preface|acknowledg)\b",
            folded(first_body["text"]),
        )
        and first_body["role"] == "heading"
    )
    if front_intro:
        first_body = next(
            (
                b
                for b in candidates
                if b["role"] == "heading"
                and re.match(
                    r"^(chuong|chapter|phan|part)\s+(?:1|i)\b", folded(b["text"])
                )
            ),
            first_body,
        )
        front_intro = first_body is not candidates[0]
    body_first = analysis.elements[first_body["id"]]
    segments = []
    if editor.cover_end:
        section = (
            cover_section
            if cover_section is not None
            else _boundary(
                editor,
                front[0] if front else analysis.elements[candidates[0]["id"]],
                template,
                "cover",
            )
        )
        segments.append(("cover", section))
    if front or front_intro:
        segments.append(("front", _boundary(editor, body_first, template, "front")))
    appendix = next(
        (
            b
            for b in candidates
            if b.get("region") == "appendices" and b["role"] == "heading"
        ),
        None,
    )
    if appendix and appendix["id"] != candidates[0]["id"]:
        segments.append(
            (
                "body",
                _boundary(editor, analysis.elements[appendix["id"]], template, "body"),
            )
        )
        segments.append(("appendix", template))
    else:
        segments.append(("body", template))
    original_nodes, original_sections = analysis.section_nodes, analysis.sections
    preserved_cover = cover_section is not None and any(
        editor.analysis.elements[bid] in cover_section.iterancestors()
        for bid in editor.locked
    )
    numbered_segments = [
        (kind, section)
        for kind, section in segments
        if not (preserved_cover and kind == "cover")
    ]
    analysis.section_nodes = [
        (i, section) for i, (_, section) in enumerate(numbered_segments)
    ]
    analysis.sections = [{"complex": False} for _ in numbered_segments]
    try:
        add_page_numbers(editor)
    finally:
        analysis.section_nodes, analysis.sections = original_nodes, original_sections
    if not editor.numbering_applied:
        return
    for kind, section in segments:
        if kind == "cover" and preserved_cover:
            editor.warn(
                "cover_footer_preserved",
                "Giữ chân trang bìa đang khóa",
                "Đánh số học thuật từ phần đầu và thân bài; chân trang bìa giữ như bản gốc.",
            )
            continue
        values = {"fmt": "lowerRoman" if kind == "front" else "decimal"}
        if kind != "appendix":
            values["start"] = 1
        editor.prop(section, "pgNumType", values, ("start",))
        editor.prop(section, "titlePg", {"val": int(kind == "cover")})
        if kind == "cover" and editor.options.cover == "academic":
            editor.prop(section, "vAlign", {"val": "center"})
            border = ensure(section, "pgBorders")
            for key, value in {"offsetFrom": "page", "display": "firstPage"}.items():
                border.set(q(key), value)
            for side in ("top", "left", "bottom", "right"):
                editor.prop(
                    border,
                    side,
                    {
                        "val": "single",
                        "sz": 8,
                        "space": 24,
                        "color": editor.design.accent,
                    },
                )
        elif kind != "cover":
            editor.prop(section, "vAlign", {"val": "top"})
    editor.academic_numbering = True
    editor.academic_body_id = first_body["id"]
    editor.log(
        "page_numbers",
        None,
        "academic_sections",
        len(segments),
        sections=[kind for kind, _ in segments],
    )
