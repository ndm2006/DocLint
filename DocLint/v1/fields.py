"""User-approved generated TOC and page fields; original parts stay recoverable."""

from copy import deepcopy
import posixpath
import re
from urllib.parse import unquote, urlsplit
from lxml import etree
from core.processor import DocumentError
from core.xmlutils import NS, q
from v1.analysis import plain, text_of
from v1.design import ensure, attrs
from v1.package import CT, PKG, R


def run_text(text):
    run = etree.Element(q("r"))
    node = etree.SubElement(run, q("t"))
    node.text = text
    if text.startswith(" ") or text.endswith(" "):
        node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return run


def field(kind, cached="1"):
    node = etree.Element(q("fldSimple"), {q("instr"): f" {kind} ", q("dirty"): "true"})
    node.append(run_text(cached))
    return node


def _ends_page(node):
    if node is None:
        return False
    section = node.find("w:pPr/w:sectPr", NS)
    if section is not None:
        kind = section.find(q("type"))
        if kind is None or kind.get(q("val")) != "continuous":
            return True
    last = None
    for child in node.iter():
        if (
            child.tag in {q("br"), q("drawing"), q("pict")}
            or child.tag == q("t")
            and child.text
        ):
            last = child
    return last is not None and last.tag == q("br") and last.get(q("type")) == "page"


def _flow_before(node):
    previous = node.getprevious()
    while previous is not None and previous.tag not in {q("p"), q("tbl"), q("sdt")}:
        previous = previous.getprevious()
    return previous


def _separate_before(editor, node, rule):
    if node is None or _ends_page(_flow_before(node)):
        return
    block_id = next(
        (bid for bid, element in editor.analysis.elements.items() if element is node),
        None,
    )
    if node.tag == q("p"):
        existing = editor.analysis.resolver.property(node, "w:pPr/w:pageBreakBefore")
        if existing is not None and existing.get(q("val"), "1") not in {
            "0",
            "false",
            "off",
        }:
            return
        if block_id not in editor.locked:
            editor.prop(ensure(node, "pPr"), "pageBreakBefore", {"val": 1})
            editor.log(rule, block_id, "separate_page")
            return
    # A generated separator leaves locked paragraphs and tables unchanged.
    marker = etree.Element(q("p"))
    props = ensure(marker, "pPr")
    attrs(props, "pageBreakBefore", {"val": 1})
    attrs(props, "keepNext", {"val": 1})
    attrs(props, "spacing", {"before": 0, "after": 0, "line": 20, "lineRule": "exact"})
    parent = node.getparent()
    editor.ledger.append_generated(parent, marker, rule, list(parent).index(node))
    editor.log(rule, block_id, "separate_page_preserving_lock")


def _trim_boundary_padding(editor, start):
    body = editor.analysis.body
    if editor.options.mode != "layout":
        return
    for node in list(body)[start:]:
        block_id = next(
            (
                bid
                for bid, element in editor.analysis.elements.items()
                if element is node
            ),
            None,
        )
        if (
            node.tag != q("p")
            or text_of(node).strip(" ")
            or block_id in editor.locked
            or block_id is None
        ):
            break
        removed = editor.ledger.trim_leading(node, block_id, permit_tabs=True)
        if removed:
            editor.log("whitespace", block_id, "frontmatter_padding", removed)
        if not editor.ledger.remove_empty(node, block_id):
            break
        editor.log("empty_paragraphs", block_id, "frontmatter_padding")


def separate_cover(editor):
    body = editor.analysis.body
    if editor.options.mode == "layout":
        for block in editor.analysis.blocks:
            if block["position"] > editor.cover_position:
                break
            node = editor.analysis.elements[block["id"]]
            if (
                block["id"] not in editor.locked
                and node.tag == q("p")
                and not text_of(node)
                and editor.ledger.remove_empty(node, block["id"])
            ):
                editor.log("empty_paragraphs", block["id"], "cover_padding")
    covered = [
        editor.analysis.elements[b["id"]]
        for b in editor.analysis.blocks
        if b["position"] <= editor.cover_position
        and editor.analysis.elements[b["id"]].getparent() is body
    ]
    if not covered:
        raise DocumentError("Phần bìa không có nội dung để trình bày.")
    start = list(body).index(covered[-1]) + 1
    _trim_boundary_padding(editor, start)
    following = next(
        (n for n in list(body)[start:] if n.tag in {q("p"), q("tbl"), q("sdt")}), None
    )
    _separate_before(editor, following, "cover")


def create_toc(editor):
    analysis, ledger = editor.analysis, editor.ledger
    headings = {b["id"]: b for b in editor.heading_blocks}
    for block in analysis.blocks:
        if (
            block["role"] == "heading"
            and block["certainty"] == "certain"
            and block["position"] > editor.cover_position
        ):
            headings.setdefault(block["id"], block)
    headings = [
        {**b, "text": plain(text_of(analysis.elements[b["id"]]))}
        for b in sorted(headings.values(), key=lambda b: b["position"])
    ]
    if not headings:
        raise DocumentError(
            "Cần có ít nhất một Heading đã có hoặc tiêu đề được duyệt trước khi tạo mục lục."
        )
    body = analysis.body
    if editor.options.toc == "replace":
        if any(analysis.elements[bid] in analysis.toc_nodes for bid in editor.locked):
            raise DocumentError(
                "Mục lục nằm trong vùng khóa. Hãy bỏ khóa vùng đó trước khi thay thế."
            )
        index = list(body).index(analysis.toc_nodes[0])
        ledger.replace_toc(analysis.toc_nodes)
    else:
        index = 0
        if editor.cover_end:
            cover_last = next(
                analysis.elements[b["id"]]
                for b in reversed(analysis.blocks)
                if b["position"] <= editor.cover_position
                and analysis.elements[b["id"]].getparent() is body
            )
            index = list(body).index(cover_last) + 1
    _trim_boundary_padding(editor, index)
    previous = next(
        (
            n
            for n in reversed(list(body)[:index])
            if n.tag in {q("p"), q("tbl"), q("sdt")}
        ),
        None,
    )
    scope_number = 1
    names = set(
        package_name
        for package_name in editor.package.document.xpath(
            ".//w:bookmarkStart/@w:name", namespaces=NS
        )
    )
    while f"DocLintBody{scope_number}" in names:
        scope_number += 1
    scope_name = f"DocLintBody{scope_number}"
    sdt = etree.Element(q("sdt"))
    sp = etree.SubElement(sdt, q("sdtPr"))
    etree.SubElement(sp, q("tag"), {q("val"): "DocLintTOC"})
    part = etree.SubElement(sp, q("docPartObj"))
    etree.SubElement(part, q("docPartGallery"), {q("val"): "Table of Contents"})
    content = etree.SubElement(sdt, q("sdtContent"))
    title = etree.SubElement(content, q("p"))
    props = ensure(title, "pPr")
    attrs(props, "pStyle", {"val": editor.design.style("heading", 1)})
    # TOC title must not become an entry in its own TOC.
    attrs(props, "outlineLvl", {"val": 9})
    attrs(props, "keepNext", {"val": 1})
    if not _ends_page(previous):
        attrs(props, "pageBreakBefore", {"val": 1})
    title.append(run_text("MỤC LỤC"))
    start = etree.SubElement(content, q("p"))
    run = etree.SubElement(start, q("r"))
    etree.SubElement(run, q("fldChar"), {q("fldCharType"): "begin", q("dirty"): "true"})
    instruction = etree.SubElement(etree.SubElement(start, q("r")), q("instrText"))
    instruction.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instruction.text = f' TOC \\b "{scope_name}" \\o "1-6" \\h \\z \\u '
    etree.SubElement(
        etree.SubElement(start, q("r")), q("fldChar"), {q("fldCharType"): "separate"}
    )
    attrs(ensure(start, "pPr"), "keepNext", {"val": 1})
    attrs(
        ensure(start, "pPr"),
        "spacing",
        {"before": 0, "after": 0, "line": 20, "lineRule": "exact"},
    )
    toc_width = editor._available_width(headings[0]) - 80
    for heading in headings:
        p = etree.SubElement(content, q("p"))
        pp = ensure(p, "pPr")
        attrs(pp, "pStyle", {"val": editor.design.style("toc", heading["level"])})
        tabs = ensure(pp, "tabs")
        etree.SubElement(
            tabs,
            q("tab"),
            {q("val"): "right", q("leader"): "dot", q("pos"): str(toc_width)},
        )
        p.append(run_text(heading["text"]))
        etree.SubElement(etree.SubElement(p, q("r")), q("tab"))
        number_run = run_text("…")
        p.append(number_run)
        editor.toc_entries.append(
            {
                "block_id": heading["id"],
                "text": heading["text"],
                "level": heading["level"],
                "node": number_run.find(q("t")),
                "page": None,
            }
        )
    end = etree.SubElement(content, q("p"))
    etree.SubElement(
        etree.SubElement(end, q("r")), q("fldChar"), {q("fldCharType"): "end"}
    )
    attrs(
        ensure(end, "pPr"),
        "spacing",
        {"before": 0, "after": 0, "line": 20, "lineRule": "exact"},
    )
    ledger.append_generated(body, sdt, "toc", index)
    editor.generated_toc = sdt
    # Start *all* body content after the TOC, including introduction paragraphs
    # before the first heading. Locked content uses a generated separator.
    following = next(
        (n for n in list(body)[index + 1 :] if n.tag in {q("p"), q("tbl"), q("sdt")}),
        None,
    )
    _separate_before(editor, following, "toc")
    bookmark_id = str(
        max(
            [
                int(v)
                for v in editor.package.document.xpath(
                    ".//w:bookmarkStart/@w:id", namespaces=NS
                )
                if v.isdigit()
            ]
            + [0]
        )
        + 1
    )
    ledger.append_generated(
        body,
        etree.Element(
            q("bookmarkStart"), {q("id"): bookmark_id, q("name"): scope_name}
        ),
        "toc_scope",
        list(body).index(sdt) + 1,
    )
    end_at = next(
        (i for i, child in enumerate(body) if child.tag == q("sectPr")), len(body)
    )
    ledger.append_generated(
        body,
        etree.Element(q("bookmarkEnd"), {q("id"): bookmark_id}),
        "toc_scope",
        end_at,
    )
    editor.log(
        "toc",
        None,
        "replace" if editor.options.toc == "replace" else "insert",
        len(headings),
    )
    update_fields_setting(editor)


def update_fields_setting(editor):
    package, ledger = editor.package, editor.ledger
    if "word/settings.xml" in package.parts:
        root = ledger.track("word/settings.xml")
        node = root.find(q("updateFields"))
        if node is None:
            following = {
                "hdrShapeDefaults",
                "footnotePr",
                "endnotePr",
                "compat",
                "docVars",
                "rsids",
                "mathPr",
                "themeFontLang",
                "clrSchemeMapping",
                "doNotIncludeSubdocsInStats",
                "doNotAutoCompressPictures",
                "forceUpgrade",
                "captions",
                "decimalSymbol",
                "listSeparator",
            }
            at = next(
                (
                    i
                    for i, c in enumerate(root)
                    if isinstance(c.tag, str) and etree.QName(c).localname in following
                ),
                len(root),
            )
            ledger.append_generated(
                root,
                etree.Element(q("updateFields"), {q("val"): "true"}),
                "field_update_setting",
                at,
            )
        else:
            node.set(q("val"), "true")
            ledger.pairs[node].set(q("val"), "true")


def _relationships(editor):
    name = "word/_rels/document.xml.rels"
    if name in editor.package.parts:
        return editor.ledger.track(name)
    root = etree.Element(f"{{{PKG}}}Relationships", nsmap={None: PKG})
    editor.ledger.new_part(name, root, "document_relationships")
    return root


def _resolve_part(source, target):
    parsed = urlsplit(target or "")
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Invalid internal relationship")
    path = unquote(parsed.path)
    resolved = posixpath.normpath(
        path.lstrip("/")
        if path.startswith("/")
        else posixpath.join(posixpath.dirname(source), path)
    )
    if not path or resolved.startswith("../") or "\\" in resolved:
        raise ValueError("Invalid package path")
    return resolved


def _rels_name(name):
    return posixpath.join(
        posixpath.dirname(name), "_rels", posixpath.basename(name) + ".rels"
    )


def _footer_part(editor, root, suffix, source_name=None):
    package, ledger = editor.package, editor.ledger
    n = 1
    while (
        f"word/doclint_{suffix}{n}.xml" in package.parts
        or f"word/doclint_{suffix}{n}.xml" in package.roots
    ):
        n += 1
    name = f"word/doclint_{suffix}{n}.xml"
    if source_name and _rels_name(source_name) in package.parts:
        cloned = deepcopy(package.xml(_rels_name(source_name)))
        for rel in cloned:
            if rel.get("TargetMode") != "External":
                rel.set("Target", "/" + _resolve_part(source_name, rel.get("Target")))
        ledger.new_part(_rels_name(name), cloned, "footer_relationships")
    # Cloned drawings need fresh document-wide IDs; the source parts stay intact.
    wp = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    for node in root.iter(f"{{{wp}}}docPr"):
        editor.footer_drawing_id += 1
        node.set("id", str(editor.footer_drawing_id))
    ledger.new_part(name, root, "page_numbers")
    relationships = _relationships(editor)
    ids = {n.get("Id") for n in relationships}
    number = 1
    while f"rIdDocLint{number}" in ids:
        number += 1
    rid = f"rIdDocLint{number}"
    rel = etree.Element(
        f"{{{PKG}}}Relationship",
        {"Id": rid, "Type": f"{R}/footer", "Target": name.removeprefix("word/")},
    )
    ledger.append_generated(relationships, rel, "page_numbers_relationship")
    content_types = ledger.track("[Content_Types].xml")
    override = etree.Element(
        f"{{{CT}}}Override",
        {
            "PartName": "/" + name,
            "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
        },
    )
    ledger.append_generated(content_types, override, "page_numbers_content_type")
    return rid


def _page_instruction(value):
    return bool(re.match(r"^\s*PAGE(?:\s|$)", value or "", re.I))


def _contains_page(root):
    return any(
        _page_instruction(v)
        for v in root.xpath(".//w:fldSimple/@w:instr", namespaces=NS)
    ) or any(
        _page_instruction(instruction) for _, _, instruction in _complex_fields(root)
    )


def _enabled(node):
    return node is not None and node.get(q("val"), "true").lower() not in {
        "0",
        "false",
        "off",
    }


def _hide_page(root):
    for simple in root.xpath(".//w:fldSimple", namespaces=NS):
        if _page_instruction(simple.get(q("instr"))):
            simple.getparent().remove(simple)
    for paragraph, segment, instruction in _complex_fields(root):
        if _page_instruction(instruction):
            for run in segment:
                paragraph.remove(run)


def _complex_fields(root):
    # Preflight has rejected nested fields. Word may split PAGE across runs.
    for p in root.xpath(".//w:p", namespaces=NS):
        children = list(p)
        start = None
        for index, run in enumerate(children):
            if run.tag != q("r"):
                continue
            if run.find('w:fldChar[@w:fldCharType="begin"]', NS) is not None:
                start = index
            if (
                start is not None
                and run.find('w:fldChar[@w:fldCharType="end"]', NS) is not None
            ):
                segment = children[start : index + 1]
                instruction = "".join(
                    "".join(r.xpath(".//w:instrText/text()", namespaces=NS))
                    for r in segment
                )
                yield p, segment, instruction
                start = None


def _safe_footer(root):
    """Only edit standalone, balanced fields; nested IF/PAGE must stay untouched."""
    for paragraph in root.iter(q("p")):
        depth = 0
        for node in paragraph.iter():
            if node.tag == q("fldSimple") and depth:
                return False
            if node.tag == q("fldChar"):
                kind = node.get(q("fldCharType"))
                if kind == "begin":
                    if depth or node.getparent().getparent() is not paragraph:
                        return False
                    if node.getparent().find(q("t")) is not None:
                        return False
                    depth = 1
                elif kind == "end":
                    if not depth or node.getparent().getparent() is not paragraph:
                        return False
                    if node.getparent().find(q("t")) is not None:
                        return False
                    depth = 0
            elif (
                depth
                and node.tag not in {q("r"), q("rPr"), q("instrText"), q("t")}
                and not any(a.tag == q("rPr") for a in node.iterancestors())
            ):
                return False
        if depth:
            return False
    return not root.xpath(
        ".//w:fldSimple//w:fldSimple | .//w:fldSimple//w:fldChar", namespaces=NS
    )


def add_page_numbers(editor):
    package, ledger = editor.package, editor.ledger
    rels = _relationships(editor)
    source_relations = {
        r.get("Id"): r.get("Target") for r in rels if r.get("TargetMode") != "External"
    }
    # Preflight all referenced footers before changing a single section. A partial
    # numbering rewrite would make the cached TOC counters ambiguous.
    try:
        if any(s["complex"] for s in editor.analysis.sections):
            raise ValueError(
                "Section ngang hoặc nhiều cột cần giữ hệ thống số trang gốc."
            )
        if "word/settings.xml" in package.parts and _enabled(
            package.xml("word/settings.xml").find(q("evenAndOddHeaders"))
        ):
            raise ValueError(
                "Tài liệu dùng footer trang chẵn/lẻ riêng; giữ số trang gốc."
            )
        if editor.options.hide_first_page_number and editor.analysis.section_nodes:
            first_section = editor.analysis.section_nodes[0][1]
            if (
                not _enabled(first_section.find(q("titlePg")))
                and first_section.find('w:headerReference[@w:type="first"]', NS)
                is not None
                and first_section.find('w:headerReference[@w:type="default"]', NS)
                is None
            ):
                raise ValueError(
                    "Header trang đầu ẩn có cấu trúc riêng; giữ số trang gốc."
                )
        for _, section in editor.analysis.section_nodes:
            for ref in section.findall(q("footerReference")):
                name = _resolve_part(
                    "word/document.xml", source_relations.get(ref.get(f"{{{R}}}id"))
                )
                if name not in package.parts or not _safe_footer(package.xml(name)):
                    raise ValueError("Footer thiếu hoặc chứa field lồng nhau/phức tạp.")
                relationships_name = _rels_name(name)
                if relationships_name in package.parts:
                    for rel in package.xml(relationships_name):
                        if (
                            rel.get("TargetMode") != "External"
                            and _resolve_part(name, rel.get("Target"))
                            not in package.parts
                        ):
                            raise ValueError("Liên kết nội bộ của footer bị thiếu.")
    except ValueError as exc:
        editor.warn("numbering_preserved", "Giữ nguyên số trang gốc", str(exc))
        return
    wp = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    editor.footer_drawing_id = 0
    for name in package.parts:
        if (
            name.startswith("word/")
            and name.endswith(".xml")
            and (name == "word/document.xml" or "footer" in name or "header" in name)
        ):
            for node in package.xml(name).iter(f"{{{wp}}}docPr"):
                try:
                    editor.footer_drawing_id = max(
                        editor.footer_drawing_id, int(node.get("id", "0"))
                    )
                except ValueError:
                    pass
    inherited_footer = None
    inherited_header = None
    for index, (_, section) in enumerate(editor.analysis.section_nodes):
        default = section.find('w:footerReference[@w:type="default"]', NS)
        header = section.find('w:headerReference[@w:type="default"]', NS)
        if default is not None:
            inherited_footer = default.get(f"{{{R}}}id")
        if header is not None:
            inherited_header = header.get(f"{{{R}}}id")
        if editor.analysis.sections[index]["complex"]:
            editor.warn(
                "numbering_complex_section",
                "Giữ số trang của section đặc biệt",
                "Không thay footer và số trang trên section ngang/nhiều cột.",
                f"s{index + 1}",
            )
            continue
        target = source_relations.get(inherited_footer or "")
        name = _resolve_part("word/document.xml", target) if target else None
        if name and name in package.parts:
            footer = deepcopy(package.xml(name))
        else:
            footer = etree.Element(q("ftr"), nsmap={"w": NS["w"]})
        if not _contains_page(footer):
            p = etree.SubElement(footer, q("p"))
            attrs(ensure(p, "pPr"), "jc", {"val": "center"})
            p.append(field("PAGE"))
        rid = _footer_part(editor, footer, "footer", name)
        # Changing the reference is an approved footer operation, not a generic
        # formatting exception. Preserve the corresponding original part.
        if default is not None:
            default.set(f"{{{R}}}id", rid)
            ledger.pairs[default].set(f"{{{R}}}id", rid)
        else:
            new_ref = etree.Element(
                q("footerReference"), {q("type"): "default", f"{{{R}}}id": rid}
            )
            at = sum(
                1
                for n in section
                if n.tag in {q("headerReference"), q("footerReference")}
            )
            ledger.append_generated(section, new_ref, "page_numbers_reference", at)
        values = {"fmt": "decimal"}
        if index == 0:
            values["start"] = 0 if editor.options.hide_first_page_number else 1
        editor.prop(section, "pgNumType", values, ("start",))
        if index == 0 and editor.options.hide_first_page_number:
            first_was_active = _enabled(section.find(q("titlePg")))
            editor.prop(section, "titlePg", {"val": 1})
            first = section.find('w:footerReference[@w:type="first"]', NS)
            first_target = (
                source_relations.get(first.get(f"{{{R}}}id"))
                if first is not None and first_was_active
                else None
            )
            first_name = (
                _resolve_part("word/document.xml", first_target)
                if first_target
                else None
            )
            first_footer = (
                deepcopy(package.xml(first_name))
                if first_name in package.parts
                else deepcopy(footer)
            )
            _hide_page(first_footer)
            first_rid = _footer_part(
                editor, first_footer, "firstfooter", first_name or name
            )
            if first is not None:
                first.set(f"{{{R}}}id", first_rid)
                ledger.pairs[first].set(f"{{{R}}}id", first_rid)
            else:
                ledger.append_generated(
                    section,
                    etree.Element(
                        q("footerReference"),
                        {q("type"): "first", f"{{{R}}}id": first_rid},
                    ),
                    "page_numbers_reference",
                    sum(1 for n in section if n.tag == q("headerReference")),
                )
            # titlePg also changes the header: clone its reference to preserve it.
            first_header = section.find('w:headerReference[@w:type="first"]', NS)
            if first_header is not None and not first_was_active and inherited_header:
                first_header.set(f"{{{R}}}id", inherited_header)
                ledger.pairs[first_header].set(f"{{{R}}}id", inherited_header)
            elif first_header is None and inherited_header:
                ledger.append_generated(
                    section,
                    etree.Element(
                        q("headerReference"),
                        {q("type"): "first", f"{{{R}}}id": inherited_header},
                    ),
                    "first_header_preserved",
                    0,
                )
        editor.log("page_numbers", f"s{index + 1}", "arabic_footer")
    update_fields_setting(editor)
    editor.numbering_applied = True
