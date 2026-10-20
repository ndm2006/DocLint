"""Convert only approved, consecutive plain manual lists, preserving labels."""

import re
from lxml import etree
from core.xmlutils import NS, ORDERS, q
from v1.analysis import text_of
from v1.design import ensure, attrs
from v1.fields import _relationships
from v1.package import CT, PKG, R


def _numbering(editor):
    name = "word/numbering.xml"
    if name in editor.package.parts:
        return editor.ledger.track(name)
    root = etree.Element(q("numbering"), nsmap={"w": NS["w"]})
    editor.ledger.new_part(name, root, "native_list")
    rels = _relationships(editor)
    ids = {r.get("Id") for r in rels}
    rid = "rIdDocLintNumbering"
    while rid in ids:
        rid += "x"
    editor.ledger.append_generated(
        rels,
        etree.Element(
            f"{{{PKG}}}Relationship",
            {"Id": rid, "Type": R + "/numbering", "Target": "numbering.xml"},
        ),
        "numbering_relationship",
    )
    types = editor.ledger.track("[Content_Types].xml")
    editor.ledger.append_generated(
        types,
        etree.Element(
            f"{{{CT}}}Override",
            {
                "PartName": "/" + name,
                "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml",
            },
        ),
        "numbering_content_type",
    )
    return root


def convert_lists(editor):
    if editor.options.mode != "layout":
        editor.warn(
            "manual_list_strict",
            "Giữ tiền tố danh sách ở chế độ giữ ký tự",
            "Chuyển sang danh sách Word cần chế độ làm sạch có kiểm soát; không xóa tiền tố gốc trong chế độ strict.",
        )
        return
    groups, current = [], []
    for b in editor.analysis.blocks:
        match = (
            re.match(r"^(\d+)([.)])(\s+)", text_of(editor.analysis.elements[b["id"]]))
            if b["type"] == "paragraph"
            else None
        )
        eligible = (
            b["role"] == "manual_list"
            and b["id"] not in editor.locked
            and b["position"] > editor.cover_position
            and not b.get("region")
            and not b.get("complex_section")
            and b["id"] not in editor.options.heading_levels
        )
        if not eligible or not match:
            if len(current) >= 2:
                groups.append(current)
            current = []
            continue
        if current and (
            int(match[1]) != int(current[-1][1][1]) + 1 or match[2] != current[-1][1][2]
        ):
            if len(current) >= 2:
                groups.append(current)
            current = []
        current.append((b, match))
    if len(current) >= 2:
        groups.append(current)
    if not groups:
        return
    root = _numbering(editor)
    abstract_id = (
        max(
            [
                int(v)
                for v in root.xpath("./w:abstractNum/@w:abstractNumId", namespaces=NS)
                if v.isdigit()
            ]
            + [-1]
        )
        + 1
    )
    num_id = (
        max(
            [
                int(v)
                for v in root.xpath("./w:num/@w:numId", namespaces=NS)
                if v.isdigit()
            ]
            + [0]
        )
        + 1
    )
    for members in groups:
        # A prefix split across runs, zero-padded labels or embedded fields must
        # stay unchanged; never partly convert a list.
        targets = []
        for b, match in members:
            p = editor.analysis.elements[b["id"]]
            first = next(iter(p.findall(q("r"))), None)
            node = first.find(q("t")) if first is not None else None
            if (
                node is None
                or not (node.text or "").startswith(match[0])
                or (len(match[1]) > 1 and match[1].startswith("0"))
                or any(n.tag not in {q("rPr"), q("t")} for n in first)
            ):
                targets = []
                break
            targets.append((b, match, node))
        if not targets:
            editor.warn(
                "manual_list_complex",
                "Giữ danh sách có tiền tố phức tạp",
                "Chưa đổi số gõ tay khi không thể giữ chính xác nhãn hiện có.",
            )
            continue
        abstract = etree.Element(
            q("abstractNum"), {q("abstractNumId"): str(abstract_id)}
        )
        attrs(abstract, "multiLevelType", {"val": "singleLevel"})
        level = etree.SubElement(abstract, q("lvl"), {q("ilvl"): "0"})
        attrs(level, "start", {"val": int(members[0][1][1])})
        attrs(level, "numFmt", {"val": "decimal"})
        attrs(level, "lvlText", {"val": "%1" + members[0][1][2]})
        attrs(level, "lvlJc", {"val": "left"})
        attrs(level, "suff", {"val": "space"})
        attrs(ensure(level, "pPr"), "ind", {"left": 360, "hanging": 360})
        first_num = next(
            (i for i, n in enumerate(root) if n.tag == q("num")), len(root)
        )
        editor.ledger.append_generated(
            root, abstract, "native_list_definition", first_num
        )
        number = etree.Element(q("num"), {q("numId"): str(num_id)})
        attrs(number, "abstractNumId", {"val": abstract_id})
        editor.ledger.append_generated(root, number, "native_list_instance")
        for b, match, node in targets:
            editor.ledger.consume_list_prefix(node, match[0], b["id"])
            pp = ensure(editor.analysis.elements[b["id"]], "pPr")
            props = etree.Element(q("numPr"))
            attrs(props, "ilvl", {"val": 0})
            attrs(props, "numId", {"val": num_id})
            # Register numbering as an explicit content-preserving label move,
            # not as an ignorable generic formatting property.
            ranks = {q(name): rank for rank, name in enumerate(ORDERS["pPr"])}
            order = next(
                (
                    i
                    for i, n in enumerate(pp)
                    if ranks.get(n.tag, 999) > ranks[q("numPr")]
                ),
                len(pp),
            )
            editor.ledger.append_generated(pp, props, "native_list_numbering", order)
            editor.log(
                "lists", b["id"], "manual_to_native_list", label=match[1] + match[2]
            )
        abstract_id += 1
        num_id += 1
