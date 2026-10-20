"""Conservative glossary extraction and explicitly requested signature placement."""

from collections import defaultdict
import re
from lxml import etree
from core.xmlutils import NS, q
from v1.analysis import folded, plain, text_of
from v1.design import attrs, ensure
from v1.fields import _separate_before, run_text


def position_signature(editor):
    blocks = editor.analysis.blocks
    found = [
        b
        for b in blocks
        if b["role"] == "signature"
        and b["position"] > editor.cover_position
        and not b.get("region")
    ]
    if len(found) != 1:
        editor.warn(
            "signature_ambiguous",
            "Giữ vị trí chữ ký chưa rõ",
            "Chỉ tự chuyển khi xác định được duy nhất một khối chữ ký ở thân bài.",
        )
        return
    label = found[0]
    group = [label]
    for b in blocks[blocks.index(label) + 1 :]:
        if not b["text"]:
            break
        words = b["text"].split()
        name = 2 <= len(words) <= 6 and all(
            w[0].isupper() and all(c.isalpha() or c in "'-" for c in w) for w in words
        )
        if b["role"] == "body" and name:
            group.append(b)
        else:
            if (
                b["role"] == "body"
                and len(b["text"]) < 100
                and not b["text"].endswith((".", "!", "?", ":"))
            ):
                editor.warn(
                    "signature_ambiguous",
                    "Giữ khối chữ ký có thông tin chưa rõ",
                    "Chưa đủ căn cứ tách nhãn chữ ký khỏi dòng tên/thông tin kế tiếp; hãy điều chỉnh trong Word.",
                    label["id"],
                )
                return
            break
    if any(b["id"] in editor.locked or b.get("complex_section") for b in group):
        editor.warn(
            "signature_locked",
            "Giữ chữ ký trong vùng khóa",
            "Không chuyển một phần khối chữ ký đang được bảo vệ.",
            label["id"],
        )
        return
    target_block = next(
        (
            b
            for b in blocks
            if b["position"] > group[-1]["position"]
            and b.get("region")
            and b["role"] == "heading"
        ),
        None,
    )
    target = (
        editor.analysis.elements[target_block["id"]]
        if target_block
        else editor.analysis.body.find(q("sectPr"))
    )
    if target is None:
        return
    nodes = [editor.analysis.elements[b["id"]] for b in group]
    if nodes[-1].getnext() is target:
        return
    editor.ledger.move_signature(nodes, target)
    editor.log("body", label["id"], "signature_end_of_body", len(group))


def glossary(editor):
    a = editor.analysis
    if editor.package.document.xpath(
        './/w:sdtPr/w:tag[@w:val="DocLintGlossary"]', namespaces=NS
    ) or any(
        re.match(
            r"^(danh muc (?:tu )?viet tat|abbreviations|glossary)\b", folded(b["text"])
        )
        for b in a.blocks
    ):
        return
    candidates = defaultdict(set)
    for b in a.blocks:
        if (
            b["position"] <= editor.cover_position
            or b["id"] in editor.locked
            or b.get("region")
            or b["role"] in {"code", "protected"}
        ):
            continue
        node = a.elements[b["id"]]
        if b["type"] == "paragraph":
            match = re.fullmatch(
                r"\s*([A-Z][A-Z0-9]{1,9})\s*[:=–—-]\s+(.{5,160}?)\s*", text_of(node)
            )
            if match and not re.fullmatch(r"(?:FR|NFR|REQ|UC|TC|ID)\d+", match[1]):
                candidates[match[1]].add(match[2])
        elif b["type"] == "table":
            rows = node.findall(q("tr"))
            if not rows:
                continue
            header = folded(plain(text_of(rows[0])))
            if not (
                "viet tat" in header or "acronym" in header or "abbreviation" in header
            ):
                continue
            for row in rows[1:]:
                cells = row.findall(q("tc"))
                if len(cells) == 2:
                    code, meaning = (plain(text_of(c)) for c in cells)
                    if (
                        re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", code)
                        and 5 <= len(meaning) <= 160
                    ):
                        candidates[code].add(meaning)
    entries = [
        (code, next(iter(meanings)))
        for code, meanings in sorted(candidates.items())
        if len(meanings) == 1
    ]
    if any(len(v) > 1 for v in candidates.values()):
        editor.warn(
            "glossary_ambiguous",
            "Có từ viết tắt được giải thích khác nhau",
            "Chỉ đưa các cặp mã–định nghĩa rõ ràng vào danh mục; không tự hợp nhất các nghĩa khác nhau.",
        )
    if len(entries) < 2:
        technical = {
            "API",
            "DOCX",
            "PDF",
            "XML",
            "HTTP",
            "SQL",
            "JSON",
            "REST",
            "GUI",
            "CPU",
        }
        present = technical.intersection(
            re.findall(r"\b[A-Z]{2,6}\b", " ".join(b["text"] for b in a.blocks))
        )
        if len(present) >= 3:
            editor.warn(
                "glossary_definitions_missing",
                "Chưa đủ định nghĩa để tạo danh mục viết tắt",
                "Có các từ viết tắt nhưng thiếu cặp mã–giải thích rõ ràng. Không tự suy diễn nghĩa; hãy bổ sung định nghĩa vào tài liệu gốc nếu cần danh mục.",
            )
        return
    container = etree.Element(q("sdt"))
    props = etree.SubElement(container, q("sdtPr"))
    etree.SubElement(props, q("tag"), {q("val"): "DocLintGlossary"})
    content = etree.SubElement(container, q("sdtContent"))
    title = etree.SubElement(content, q("p"))
    pp = ensure(title, "pPr")
    attrs(pp, "pStyle", {"val": editor.design.style("heading", 1)})
    attrs(pp, "outlineLvl", {"val": 9})
    attrs(pp, "pageBreakBefore", {"val": 1})
    attrs(pp, "keepNext", {"val": 1})
    title.append(run_text("DANH MỤC TỪ VIẾT TẮT"))
    table = etree.SubElement(content, q("tbl"))
    width = editor._available_width(a.blocks[0])
    table_props = ensure(table, "tblPr")
    attrs(table_props, "tblW", {"w": width, "type": "dxa"})
    attrs(table_props, "tblLayout", {"type": "fixed"})
    borders = ensure(table_props, "tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        attrs(borders, edge, {"val": "single", "sz": 4, "color": "CDD6CD"})
    grid = etree.SubElement(table, q("tblGrid"))
    widths = [width // 4, width - width // 4]
    for value in widths:
        etree.SubElement(grid, q("gridCol"), {q("w"): str(value)})
    for index, pair in enumerate(
        [("Viết tắt", "Giải thích theo tài liệu gốc")] + entries
    ):
        row = etree.SubElement(table, q("tr"))
        attrs(ensure(row, "trPr"), "cantSplit", {"val": 1})
        if index == 0:
            attrs(ensure(row, "trPr"), "tblHeader", {"val": 1})
        for value, cell_width in zip(pair, widths):
            cell = etree.SubElement(row, q("tc"))
            attrs(ensure(cell, "tcPr"), "tcW", {"w": cell_width, "type": "dxa"})
            if index == 0:
                attrs(ensure(cell, "tcPr"), "shd", {"fill": "EAF0E8", "val": "clear"})
            p = etree.SubElement(cell, q("p"))
            attrs(ensure(p, "pPr"), "pStyle", {"val": editor.design.style("table")})
            attrs(ensure(p, "pPr"), "keepNext", {"val": int(index == 0)})
            p.append(run_text(value))
    front = getattr(editor, "frontmatter_nodes", [])
    previous = front[-1] if front else editor.generated_toc
    body = a.body
    if previous is not None:
        index = list(body).index(previous) + 1
    elif a.toc_nodes:
        index = list(body).index(a.toc_nodes[-1]) + 1
    else:
        first = next(
            (
                b
                for b in a.blocks
                if b["position"] > editor.cover_position and b["text"]
            ),
            None,
        )
        if first is None:
            return
        index = list(body).index(a.elements[first["id"]])
    editor.ledger.append_generated(body, container, "glossary", index)
    editor.frontmatter_nodes = front + [container]
    following = next(
        (n for n in list(body)[index + 1 :] if n.tag in {q("p"), q("tbl"), q("sdt")}),
        None,
    )
    _separate_before(editor, following, "toc")
    editor.log("toc", None, "glossary_from_explicit_definitions", len(entries))
