"""Optional native Word fields, derived only from existing captions and labels."""

from collections import defaultdict
from copy import deepcopy
import re
from lxml import etree
from core.xmlutils import NS, q
from v1.analysis import folded, text_of, plain
from v1.design import attrs, ensure
from v1.fields import run_text, _separate_before, defer_field_updates

CAPTION_LABEL = re.compile(
    r"^(Hình|Figure|Bảng|Table)\s+(\d+(?:[.\-]\d+)*)(?=[.:\s]|$)", re.I
)


def complex_field(instruction, cached, original=None):
    nodes = []
    for kind in ("begin", "instruction", "separate", "result", "end"):
        run = etree.Element(q("r"))
        if original is not None and original.find(q("rPr")) is not None:
            run.append(deepcopy(original.find(q("rPr"))))
        if kind == "instruction":
            node = etree.SubElement(run, q("instrText"))
            node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            node.text = f" {instruction} "
        elif kind == "result":
            node = etree.SubElement(run, q("t"))
            node.text = cached or None
        else:
            etree.SubElement(
                run,
                q("fldChar"),
                {
                    q("fldCharType"): kind,
                    **({q("dirty"): "false"} if kind == "begin" else {}),
                },
            )
        nodes.append(run)
    return nodes


def _text(text, original):
    run = run_text(text)
    props = original.find(q("rPr"))
    if props is not None:
        run.insert(0, deepcopy(props))
    return run


def captions(editor):
    grouped = defaultdict(list)
    sources = []
    for b in editor.analysis.blocks:
        if (
            b["role"] != "caption"
            or b["id"] in editor.locked
            or b.get("complex_section")
            or b["position"] <= editor.cover_position
        ):
            continue
        p = editor.analysis.elements[b["id"]]
        text = text_of(p)
        m = CAPTION_LABEL.match(text)
        target = editor.options.caption_links.get(b["id"], b.get("target"))
        if not m or not target:
            continue
        parts = tuple(int(v) for v in re.split(r"[.\-]", m[2]))
        kind = "figure" if folded(m[1]) in {"hinh", "figure"} else "table"
        row = {
            "block": b,
            "node": p,
            "text": text,
            "match": m,
            "parts": parts,
            "kind": kind,
            "label": m[0],
        }
        sources.append(row)
        grouped[(kind, parts[:-1])].append(row)
    references = {}
    existing_names = set(
        editor.package.document.xpath(".//w:bookmarkStart/@w:name", namespaces=NS)
    )
    next_id = (
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
    if editor.options.caption_fields:
        interleaved = set()
        for kind in {r["kind"] for r in sources}:
            order = [r["parts"][:-1] for r in sources if r["kind"] == kind]
            runs = [
                chapter
                for index, chapter in enumerate(order)
                if index == 0 or chapter != order[index - 1]
            ]
            if len(runs) != len(set(runs)):
                interleaved.add(kind)
        for (kind, chapter), members in grouped.items():
            if kind in interleaved:
                editor.warn(
                    "caption_chapters_interleaved",
                    "Giữ số hình/bảng có chương xen kẽ",
                    "Không tự chuyển SEQ khi chuỗi số chương quay lại phần trước; tránh thay số khi Word cập nhật.",
                )
                continue
            numbers = [row["parts"][-1] for row in members]
            if numbers != list(range(numbers[0], numbers[0] + len(numbers))) or len(
                set(numbers)
            ) != len(numbers):
                editor.warn(
                    "caption_sequence_ambiguous",
                    "Giữ số chú thích chưa nhất quán",
                    "Số hình/bảng bị trùng, nhảy hoặc đảo thứ tự; không tự đánh lại số hoặc sửa tham chiếu.",
                )
                continue
            supported = True
            for row in members:
                run = next(iter(row["node"].findall(q("r"))), None)
                number = re.search(r"\d+$", row["match"][2])[0]
                if (
                    run is None
                    or len(run.findall(q("t"))) != 1
                    or not (run.find(q("t")).text or "").startswith(row["label"])
                    or any(n.tag not in {q("rPr"), q("t")} for n in run)
                    or len(number) > 1
                    and number.startswith("0")
                ):
                    supported = False
                    break
            if not supported:
                editor.warn(
                    "caption_field_preserved",
                    "Giữ nguyên nhóm chú thích có cấu trúc phức tạp",
                    "Không chuyển một phần chuỗi số nếu có nhãn chia nhiều run hoặc số 0 đầu; tránh SEQ tính sai số sau khi cập nhật.",
                )
                continue
            sequence = "DL" + ("Figure" if kind == "figure" else "Table")
            for index, row in enumerate(members):
                p, m = row["node"], row["match"]
                run = next(iter(p.findall(q("r"))), None)
                if (
                    run is None
                    or len(run.findall(q("t"))) != 1
                    or not (run.find(q("t")).text or "").startswith(m[0])
                    or any(n.tag not in {q("rPr"), q("t")} for n in run)
                ):
                    editor.warn(
                        "caption_field_preserved",
                        "Giữ chú thích có cấu trúc phức tạp",
                        "Không tách run/field có sẵn để đổi số; nội dung chú thích được giữ.",
                        row["block"]["id"],
                    )
                    continue
                name = f"DocLintCaption{next_id}"
                while name in existing_names:
                    next_id += 1
                    name = f"DocLintCaption{next_id}"
                existing_names.add(name)
                last = re.search(r"\d+$", m[2])
                numeric_start = m.start(2) + last.start()
                numeric_text = m[2][last.start() :]
                # Explicit zero-padding cannot be reproduced by an ordinary SEQ field.
                if len(numeric_text) > 1 and numeric_text.startswith("0"):
                    editor.warn(
                        "caption_padding_preserved",
                        "Giữ số chú thích có số 0 đầu",
                        "Chưa đổi sang SEQ vì có thể mất cách ghi số gốc.",
                        row["block"]["id"],
                    )
                    continue
                reset = f" \\r {row['parts'][-1]}" if index == 0 else ""
                nodes = [
                    etree.Element(
                        q("bookmarkStart"), {q("id"): str(next_id), q("name"): name}
                    ),
                    _text(m[0][:numeric_start], run),
                ]
                nodes += complex_field(
                    f"SEQ {sequence}{reset} \\* ARABIC", numeric_text, run
                )
                nodes += [
                    etree.Element(q("bookmarkEnd"), {q("id"): str(next_id)}),
                    _text((run.find(q("t")).text or "")[m.end() :], run),
                ]
                editor.ledger.replace_plain_run(run, nodes, "caption_fields")
                row["sequence"] = sequence
                references.setdefault(row["label"], []).append(name)
                next_id += 1
                editor.log("captions", row["block"]["id"], "native_seq_caption")
        # Only exact, unique labels become cross-references. No guessed phrases.
        labels = {
            label: names[0] for label, names in references.items() if len(names) == 1
        }
        if labels:
            pattern = re.compile(
                r"(?<!\w)("
                + "|".join(re.escape(k) for k in sorted(labels, key=len, reverse=True))
                + r")(?![\w.\-])"
            )
            for b in editor.analysis.blocks:
                if (
                    b["type"] != "paragraph"
                    or b["role"] not in {"body", "list", "manual_list", "lead_in"}
                    or b["id"] in editor.locked
                    or b.get("complex_section")
                ):
                    continue
                p = editor.analysis.elements[b["id"]]
                for run in list(p.findall(q("r"))):
                    if len(run.findall(q("t"))) != 1 or any(
                        n.tag not in {q("rPr"), q("t")} for n in run
                    ):
                        continue
                    text = run.find(q("t")).text or ""
                    matches = list(pattern.finditer(text))
                    if not matches:
                        continue
                    nodes, start = [], 0
                    for m in matches:
                        nodes.append(_text(text[start : m.start()], run))
                        nodes.extend(
                            complex_field(f"REF {labels[m[0]]} \\h", m[0], run)
                        )
                        start = m.end()
                    nodes.append(_text(text[start:], run))
                    editor.ledger.replace_plain_run(
                        run, nodes, "caption_cross_reference"
                    )
                    editor.log("captions", b["id"], "native_ref", len(matches))
    return sources


def object_lists(editor, sources):
    if not editor.options.object_lists:
        return
    body = editor.analysis.body
    # Do not duplicate an existing object list whose boundaries are unknown.
    if editor.package.document.xpath(
        './/w:sdtPr/w:tag[@w:val="DocLintObjectList"]', namespaces=NS
    ) or any(
        re.match(
            r"^(danh muc (?:hinh|bang)|list of (?:figures|tables))\b", folded(b["text"])
        )
        for b in editor.analysis.blocks
    ):
        editor.warn(
            "object_lists_existing",
            "Giữ danh mục hình/bảng đã có",
            "Chưa thay danh mục cũ khi chưa xác định được phạm vi an toàn; không tạo trùng.",
        )
        return
    editor.frontmatter_nodes = []
    for kind, heading, mark in [
        ("figure", "DANH MỤC HÌNH", "F"),
        ("table", "DANH MỤC BẢNG", "T"),
    ]:
        members = [s for s in sources if s["kind"] == kind]
        if not members:
            continue
        sequence = "DLFigure" if kind == "figure" else "DLTable"
        native_sequence = all(row.get("sequence") == sequence for row in members)
        for row in members if not native_sequence else []:
            instruction = (
                'TC "'
                + plain(row["text"]).replace('"', "'").replace("\\", "/")
                + f'" \\f {mark} \\l 1'
            )
            for run in complex_field(instruction, ""):
                attrs(ensure(run, "rPr"), "vanish", {"val": 1})
                editor.ledger.append_generated(row["node"], run, "object_list_marker")
        container = etree.Element(q("sdt"))
        props = etree.SubElement(container, q("sdtPr"))
        etree.SubElement(props, q("tag"), {q("val"): "DocLintObjectList"})
        content = etree.SubElement(container, q("sdtContent"))
        title = etree.SubElement(content, q("p"))
        attrs(
            ensure(title, "pPr"), "pStyle", {"val": editor.design.style("heading", 1)}
        )
        attrs(ensure(title, "pPr"), "outlineLvl", {"val": 9})
        attrs(ensure(title, "pPr"), "pageBreakBefore", {"val": 1})
        attrs(ensure(title, "pPr"), "keepNext", {"val": 1})
        title.append(run_text(heading))
        start = etree.SubElement(content, q("p"))
        instruction = (
            f'TOC \\c "{sequence}" \\h \\z'
            if native_sequence
            else f"TOC \\f {mark} \\h \\z"
        )
        if not native_sequence:
            editor.warn(
                "object_list_manual_labels",
                "Danh mục dùng nhãn chú thích được giữ nguyên",
                "Một số chú thích chưa chuyển sang SEQ. Sau khi sửa tên hoặc số chú thích trong Word, hãy xử lý lại bằng DocLint để tạo lại danh mục.",
            )
        for run in complex_field(instruction, "")[:3]:
            if (
                run.find(q("fldChar")) is not None
                and run.find(q("fldChar")).get(q("fldCharType")) == "begin"
            ):
                run.find(q("fldChar")).set(q("dirty"), "true")
            start.append(run)
        attrs(
            ensure(start, "pPr"),
            "spacing",
            {"line": 20, "lineRule": "exact", "before": 0, "after": 0},
        )
        for row in members:
            p = etree.SubElement(content, q("p"))
            pp = ensure(p, "pPr")
            attrs(pp, "pStyle", {"val": editor.design.style("toc", 1)})
            tabs = ensure(pp, "tabs")
            etree.SubElement(
                tabs,
                q("tab"),
                {
                    q("val"): "right",
                    q("leader"): "dot",
                    q("pos"): str(editor._available_width(row["block"]) - 80),
                },
            )
            p.append(run_text(plain(row["text"])))
            etree.SubElement(etree.SubElement(p, q("r")), q("tab"))
            number = run_text("…")
            p.append(number)
            editor.toc_entries.append(
                {
                    "block_id": row["block"]["id"],
                    "text": plain(row["text"]),
                    "level": 1,
                    "node": number.find(q("t")),
                    "page": None,
                    "object_list": True,
                }
            )
        end = etree.SubElement(content, q("p"))
        end.append(complex_field("", "")[-1])
        attrs(
            ensure(end, "pPr"),
            "spacing",
            {"line": 20, "lineRule": "exact", "before": 0, "after": 0},
        )
        previous = (
            editor.frontmatter_nodes[-1]
            if editor.frontmatter_nodes
            else editor.generated_toc
        )
        if previous is not None:
            index = list(body).index(previous) + 1
        elif editor.analysis.toc_nodes:
            index = list(body).index(editor.analysis.toc_nodes[-1]) + 1
        else:
            first = next(
                (
                    b
                    for b in editor.analysis.blocks
                    if b["position"] > editor.cover_position and b["text"]
                ),
                None,
            )
            index = (
                list(body).index(editor.analysis.elements[first["id"]]) if first else 0
            )
        editor.ledger.append_generated(body, container, "object_list", index)
        editor.frontmatter_nodes.append(container)
        following = next(
            (
                n
                for n in list(body)[index + 1 :]
                if n.tag in {q("p"), q("tbl"), q("sdt")}
            ),
            None,
        )
        _separate_before(editor, following, "toc")
        editor.log("toc", None, "object_list", len(members), kind=kind)
    if editor.frontmatter_nodes:
        defer_field_updates(editor)


def structural_warnings(editor):
    a = editor.analysis
    linked = {
        editor.options.caption_links.get(b["id"], b.get("target"))
        for b in a.blocks
        if b["role"] == "caption"
    }
    for b in a.blocks:
        if b["position"] <= editor.cover_position or b["id"] in editor.locked:
            continue
        if b["role"] in {"image", "table"} and b["id"] not in linked:
            editor.warn(
                "caption_missing",
                "Đối tượng chưa có chú thích nhận diện được",
                "Giữ nội dung gốc; hãy thêm tên hình/bảng trong Word nếu quy định báo cáo yêu cầu.",
                b["id"],
            )
        if b["role"] == "signature" and any(
            n["position"] > b["position"]
            and n["role"] in {"body", "list", "heading"}
            and not n.get("region")
            for n in a.blocks
        ):
            editor.warn(
                "signature_position",
                "Khối chữ ký nằm giữa nội dung",
                "Giữ thứ tự văn bản; hãy xác nhận vị trí trong Word thay vì tự chuyển chữ ký sang phần khác.",
                b["id"],
            )
    first_heading = next(
        (
            b
            for b in a.blocks
            if b["position"] > editor.cover_position
            and (
                b["id"] in editor.options.heading_levels
                or b["role"] == "heading"
                and b["certainty"] == "certain"
            )
        ),
        None,
    )
    if first_heading and any(
        b["position"] > editor.cover_position
        and b["position"] < first_heading["position"]
        and b["role"] == "body"
        and b["text"]
        for b in a.blocks
    ):
        editor.warn(
            "untitled_introduction",
            "Đoạn mở đầu chưa có tiêu đề",
            "Giữ đoạn mở đầu trong thân bài. Không tự thêm chữ “Lời mở đầu”; đoạn này không có mục riêng trong mục lục.",
        )
