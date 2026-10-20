"""Role-aware formatting. Every destructive operation has explicit consent."""

from collections import Counter
import re
import posixpath
from io import BytesIO
from PIL import Image
from core.autofix import SYMBOL_FONTS
from core.processor import DocumentError
from core.xmlutils import NS, q
from v1.analysis import Analysis, CHAPTER, PROTECTED, folded, on, plain, text_of
from v1.design import Design, ensure
from v1.cover import TITLE
from v1.options import FormatOptions
from v1.package import A, WP, IntegrityLedger, Package, canonical

LABELS = {
    "headings": "Hệ thống tiêu đề",
    "body": "Đoạn văn",
    "fonts": "Định dạng chữ",
    "paragraphs": "Khoảng cách và căn đoạn",
    "pages": "Khổ giấy và lề",
    "lists": "Danh sách và thụt treo",
    "tables": "Bảng dữ liệu",
    "images": "Ảnh trong dòng",
    "captions": "Chú thích và liên kết đối tượng",
    "cover": "Bìa",
    "whitespace": "Ký tự căn bố cục đã được phép thay",
    "empty_paragraphs": "Đoạn trống đã được phép thay",
    "toc": "Mục lục",
    "page_numbers": "Số trang",
}


class Editor:
    def __init__(self, data, options=None):
        self.source_data = data
        self.package = Package(data)
        self.analysis = Analysis(self.package)
        self.layout_locked = set(self.analysis.layout_policy["protected_block_ids"])
        self.isolated_objects = set(self.analysis.layout_policy["isolated_object_ids"])
        self.preserve_only = self.analysis.layout_policy["preserve_only"]
        self.options = (
            options
            if isinstance(options, FormatOptions)
            else FormatOptions.model_validate(options or {})
        )
        self.ledger = IntegrityLedger(self.package)
        self.changes = []
        self.warnings = []
        self.generated_toc = None
        self.toc_entries = []
        self.numbering_applied = False
        self.heading_blocks = []
        self._validate()
        self.locked = self._locks()
        for block_id in self.locked:
            self.ledger.lock(self.analysis.elements[block_id], block_id)
        for index in self.analysis.layout_policy["protected_sections"]:
            self.ledger.lock(self.analysis.section_nodes[index][1], f"s{index + 1}")
        self.design = Design(
            self.options.profile,
            self.package,
            self.ledger,
            initialize=not self.preserve_only,
        )

    def _validate(self):
        blocks = {b["id"]: b for b in self.analysis.blocks}
        if set(self.options.preserved_candidates) & set(
            self.options.unchanged_candidates
        ):
            raise DocumentError(
                "Một đoạn không thể vừa giữ nguyên định dạng vừa chuyển thành văn bản thường."
            )
        for block_id in (
            self.options.preserved_candidates + self.options.unchanged_candidates
        ):
            if (
                block_id not in blocks
                or blocks[block_id]["role"] not in {"heading", "emphasis"}
                or blocks[block_id]["certainty"] == "certain"
                or block_id in self.options.heading_levels
            ):
                raise DocumentError(
                    "Lựa chọn giữ nguyên đề mục chưa chắc chắn không hợp lệ."
                )
        for block_id in self.options.locked_blocks:
            if block_id not in blocks:
                raise DocumentError("Vùng khóa không có trong tài liệu.")
        for block_id, level in self.options.heading_levels.items():
            if (
                block_id not in blocks
                or blocks[block_id]["type"] != "paragraph"
                or blocks[block_id]["protected"]
                or blocks[block_id]["role"] in {"image", "empty", "toc"}
                or level not in range(1, 7)
            ):
                raise DocumentError("Lựa chọn cấp tiêu đề không hợp lệ.")
        for block_id in self.options.table_headers:
            if (
                block_id not in blocks
                or blocks[block_id]["type"] != "table"
                or not (
                    blocks[block_id]["simple"] or blocks[block_id].get("format_safe")
                )
            ):
                raise DocumentError(
                    "Chỉ có thể xác nhận hàng tiêu đề cho bảng đơn giản."
                )
        for block_id, decision in self.options.layout_decisions.items():
            if (
                block_id not in blocks
                or blocks[block_id]["role"] not in {"body", "signature"}
                or blocks[block_id]["protected"]
            ):
                raise DocumentError(
                    "Chỉ duyệt căn bố cục cho thân bài hoặc khối chữ ký thông thường."
                )
            if decision != "keep" and self.options.mode != "layout":
                raise DocumentError(
                    "Cần bật chế độ chuẩn hóa ký tự căn bố cục trước khi duyệt thay Space/Tab."
                )
        for block_id, target in self.options.caption_links.items():
            if (
                block_id not in blocks
                or blocks[block_id]["role"] != "caption"
                or target not in blocks[block_id].get("targets", [])
            ):
                raise DocumentError(
                    "Chỉ liên kết chú thích với ảnh/bảng liền kề đã phân tích."
                )
        # None requests detection; an empty string explicitly rejects a cover.
        end = (
            self.analysis.cover_end
            if self.options.cover_end is None
            else self.options.cover_end or None
        )
        if self.preserve_only:
            self.cover_end = self.analysis.cover_end
            self.cover_position = (
                blocks[self.cover_end]["position"] if self.cover_end else -1
            )
            return
        if self.options.cover != "keep" and (end is None or end not in blocks):
            raise DocumentError("Cần xác nhận điểm kết thúc bìa trước khi dàn lại bìa.")
        if end is not None and (end not in blocks or blocks[end]["position"] > 50):
            raise DocumentError("Phạm vi bìa không hợp lệ (tối đa 51 khối đầu).")
        if self.options.toc == "replace" and not self.analysis.toc_region:
            raise DocumentError("Không xác định được mục lục cũ để thay thế an toàn.")
        if self.options.toc == "insert" and self.analysis.toc_region:
            raise DocumentError(
                "Đã có mục lục. Chọn giữ hoặc xác nhận thay thế, tránh tạo trùng."
            )
        self.cover_end = end
        self.cover_position = blocks[end]["position"] if end else -1

    def _locks(self):
        locked = (
            set(self.options.locked_blocks)
            | set(self.options.unchanged_candidates)
            | self.layout_locked
            | self.isolated_objects
        )
        for b in self.analysis.blocks:
            if (
                self.options.preserve_cover
                and self.options.cover == "keep"
                and b["position"] <= self.cover_position
            ):
                locked.add(b["id"])
            if self.options.preserve_references and b.get("region") == "references":
                locked.add(b["id"])
            if self.options.preserve_appendices and b.get("region") == "appendices":
                locked.add(b["id"])
        return locked

    def warn(self, code, title, description, block_id=None):
        if any(
            w["code"] == code and w.get("block_id") == block_id for w in self.warnings
        ):
            return
        self.warnings.append(
            {
                "code": code,
                "title": title,
                "description": description,
                "block_id": block_id,
                "count": 1,
            }
        )

    def log(self, rule, block_id, operation, count=1, **details):
        self.changes.append(
            {
                "rule": rule,
                "title": LABELS[rule],
                "block_id": block_id,
                "operation": operation,
                "count": count,
                **details,
            }
        )

    def prop(self, parent, name, values, remove=()):
        node = parent.find(q(name))
        before = canonical(node) if node is not None else None
        node = ensure(parent, name)
        for key in remove:
            node.attrib.pop(q(key), None)
        for key, value in values.items():
            node.set(q(key), str(value))
        return before != canonical(node)

    def _fonts(self, p, spec, heading=False):
        changed = False
        for run in p.xpath(".//w:r[w:t]", namespaces=NS):
            props = run.find(q("rPr"))
            fonts = run.find("w:rPr/w:rFonts", NS)
            if fonts is None:
                style = run.find("w:rPr/w:rStyle", NS)
                if style is not None:
                    fonts = next(
                        (
                            s.find("w:rPr/w:rFonts", NS)
                            for s in self.analysis.resolver.chain(style.get(q("val")))
                            if s.find("w:rPr/w:rFonts", NS) is not None
                        ),
                        None,
                    )
            if fonts is not None and any(
                v.lower() in SYMBOL_FONTS for v in fonts.attrib.values()
            ):
                continue
            # Preserve inherited emphasis before switching paragraph styles.
            inherited = {}
            if not heading:
                for key in ("b", "i"):
                    if run.find(f"w:rPr/w:{key}", NS) is None:
                        value = self.analysis.resolver.property(p, f"w:rPr/w:{key}")
                        if on(value):
                            inherited[key] = {"val": 1}
            props = ensure(run, "rPr")
            for key, value in inherited.items():
                changed |= self.prop(props, key, value)
            changed |= self.prop(
                props,
                "rFonts",
                {"ascii": spec["font"], "hAnsi": spec["font"], "cs": spec["font"]},
                ("asciiTheme", "hAnsiTheme", "cstheme"),
            )
            if props.find(q("vertAlign")) is None:
                changed |= self.prop(props, "sz", {"val": spec["size"]})
                changed |= self.prop(props, "szCs", {"val": spec["size"]})
            if heading:
                changed |= self.prop(props, "b", {"val": 1})
                changed |= self.prop(
                    props,
                    "color",
                    {"val": spec["color"]},
                    ("themeColor", "themeTint", "themeShade"),
                )
            if spec.get("italic"):
                changed |= self.prop(props, "i", {"val": 1})
        return changed

    def paragraph(
        self, p, block, role="body", level=0, override=None, preserve_indent=False
    ):
        if p.xpath(PROTECTED, namespaces=NS):
            return False
        spec = self.design.spec(role, level)
        spec.update(override or {})
        changed = self._fonts(
            p, spec, role in {"heading", "cover"} and spec.get("bold", False)
        )
        if role == "cover":
            for run in p.xpath(".//w:r[w:t]", namespaces=NS):
                changed |= self.prop(
                    ensure(run, "rPr"), "b", {"val": int(spec["bold"])}
                )
                changed |= self.prop(
                    ensure(run, "rPr"),
                    "color",
                    {"val": spec["color"]},
                    ("themeColor", "themeTint", "themeShade"),
                )
        props = ensure(p, "pPr")
        if role != "list":  # A list's original style may supply its numbering.
            changed |= self.prop(
                props, "pStyle", {"val": self.design.style(role, level)}
            )
        changed |= self.prop(
            props,
            "spacing",
            {
                "line": spec["line"],
                "lineRule": "auto",
                "before": spec["before"],
                "after": spec["after"],
            },
            ("beforeAutospacing", "afterAutospacing", "beforeLines", "afterLines"),
        )
        changed |= self.prop(props, "jc", {"val": spec["alignment"]})
        changed |= self.prop(props, "widowControl", {"val": 1})
        changed |= self.prop(props, "keepLines", {"val": int(spec["keep_lines"])})
        changed |= self.prop(props, "keepNext", {"val": int(spec["keep_next"])})
        changed |= self.prop(props, "snapToGrid", {"val": 0})
        # Retain quotation/signature indents. Numbered list definitions retain
        # their original horizontal geometry; manual lists get a hanging indent.
        if (
            not preserve_indent
            and role != "list"
            and (
                role != "body"
                or props.find(q("ind")) is None
                or self.options.mode == "layout"
            )
        ):
            ind = {"left": spec["left"], "right": spec["right"]}
            ind["hanging" if spec["hanging"] else "firstLine"] = (
                spec["hanging"] or spec["first"]
            )
            changed |= self.prop(
                props,
                "ind",
                ind,
                (
                    "firstLine",
                    "hanging",
                    "firstLineChars",
                    "hangingChars",
                    "leftChars",
                    "rightChars",
                    "start",
                    "end",
                    "startChars",
                    "endChars",
                ),
            )
        if role == "heading":
            changed |= self.prop(props, "outlineLvl", {"val": level - 1})
        if role == "code":
            changed |= self.prop(props, "shd", {"val": "clear", "fill": "F3F5F4"})
            border = ensure(props, "pBdr")
            changed |= self.prop(
                border,
                "left",
                {"val": "single", "sz": 12, "space": 8, "color": "CCD6D0"},
            )
        if changed:
            category = {
                "heading": "headings",
                "caption": "captions",
                "list": "lists",
                "manual_list": "lists",
                "cover": "cover",
            }.get(role, "body")
            self.log(
                category, block["id"], "role_format", role=role, level=level or None
            )
        return changed

    def run(self):
        if self.layout_locked:
            self.warn(
                "positioned_layout_preserved",
                "Giữ vùng bố cục cố định",
                "Vùng có khung chữ, hộp văn bản hoặc bảng nổi và các đoạn cùng vùng được giữ nguyên. "
                "Không đổi lề/khổ giấy dùng chung, dựng lại bìa/mục lục, số trang, danh mục hoặc chuyển vị trí chữ ký. "
                "Chỉ chuẩn hóa đoạn độc lập ngoài các vùng đó.",
            )
        if self.preserve_only:
            self.warn(
                "no_editable_flow",
                "Giữ nguyên toàn bộ tài liệu",
                "Tài liệu được dựng bằng các cụm đối tượng; không có vùng văn bản độc lập đủ điều kiện sửa. "
                "Bản tải về giữ nguyên tệp gốc, chưa được chuẩn hóa theo mẫu.",
            )
            self.ledger.verify()
            return self
        blocked_sections = {
            b.get("section")
            for b in self.analysis.blocks
            if b["id"]
            in set(self.options.locked_blocks)
            | set(self.options.unchanged_candidates)
            | self.layout_locked
            | self.isolated_objects
        }
        blocked_sections.update(
            index
            for index, (_, section) in enumerate(self.analysis.section_nodes)
            if any(
                self.analysis.elements[bid] in section.iterancestors()
                for bid in self.locked
            )
        )
        for index, (_, section) in enumerate(self.analysis.section_nodes):
            if self.analysis.sections[index]["complex"] or index in blocked_sections:
                self.warn(
                    "section_preserved",
                    "Giữ nguyên section đặc biệt/được khóa",
                    "Không đổi khổ giấy và lề của section có vùng khóa, trang ngang hoặc nhiều cột.",
                    f"s{index + 1}",
                )
                continue
            changed = self.prop(section, "pgMar", self.design.profile["margin_rules"])
            changed |= self.prop(section, "pgSz", self.design.profile["page_rules"])
            if changed:
                self.log("pages", f"s{index + 1}", "page_geometry")
        last_heading = 0
        for block in self.analysis.blocks:
            block_id = block["id"]
            node = self.analysis.elements[block_id]
            if block_id in self.locked or block.get("complex_section"):
                continue
            if block["type"] == "table":
                if self.options.normalize_tables:
                    self.table(node, block)
                continue
            if block["type"] != "paragraph":
                if not (
                    self.options.toc == "replace" and node in self.analysis.toc_nodes
                ):
                    self.warn(
                        "protected_container",
                        "Giữ content control",
                        "Không sửa trực tiếp cấu trúc content control.",
                        block_id,
                    )
                continue
            if (
                self.options.cover != "keep"
                and block["position"] <= self.cover_position
            ):
                self.cover(node, block)
                continue
            if block["role"] == "code" and self.options.style_code:
                self.paragraph(node, block, "code")
                continue
            if block["role"] in {"protected", "code", "toc", "empty"}:
                continue
            if block_id in self.options.heading_levels or (
                block["role"] == "heading" and block["certainty"] == "certain"
            ):
                level = self.options.heading_levels.get(
                    block_id, block.get("level") or 1
                )
                if level > last_heading + 1:
                    self.warn(
                        "heading_gap",
                        "Cấp tiêu đề bị nhảy",
                        "Giữ nguyên lựa chọn; hãy kiểm tra lại cây chương–mục.",
                        block_id,
                    )
                last_heading = level
                self.paragraph(node, block, "heading", level)
                if level == 1 and (
                    block.get("region")
                    or any(h["level"] == 1 for h in self.heading_blocks)
                    and CHAPTER.match(folded(block["text"]))
                ):
                    from v1.fields import _separate_before

                    _separate_before(self, node, "headings")
                self.heading_blocks.append({**block, "level": level})
                continue
            if block["role"] in {"heading", "emphasis"}:
                if block_id in self.options.preserved_candidates:
                    role = (
                        "manual_list"
                        if re.match(r"^\d+[.)]\s", block["text"])
                        else "body"
                    )
                    self.paragraph(node, block, role, preserve_indent=role == "body")
                    continue
                self.warn(
                    "heading_review",
                    "Đề mục chưa được duyệt",
                    "Giữ nguyên đoạn chưa đủ căn cứ. Bạn có thể quay lại để gán cấp hoặc khóa đoạn.",
                    block_id,
                )
                continue
            if block["role"] == "image":
                if self.options.normalize_images:
                    self.image(node, block)
                continue
            if block["role"] == "caption":
                if self.options.mode == "layout" and not block["has_tab"]:
                    removed = self.ledger.trim_leading(node, block_id)
                    if removed:
                        self.log(
                            "whitespace", block_id, "caption_leading_spaces", removed
                        )
                target_id = self.options.caption_links.get(
                    block_id, block.get("target")
                )
                if target_id and target_id not in self.locked:
                    target = self.analysis.elements[target_id]
                    self.paragraph(node, block, "caption")
                    if block["position"] < next(
                        b["position"]
                        for b in self.analysis.blocks
                        if b["id"] == target_id
                    ):
                        self.prop(ensure(node, "pPr"), "keepNext", {"val": 1})
                    elif target.tag == q("p"):
                        self.prop(ensure(target, "pPr"), "keepNext", {"val": 1})
                    else:
                        self.warn(
                            "table_caption_after",
                            "Tên bảng nằm sau bảng",
                            "Giữ thứ tự gốc; cần xem lại khả năng chú thích bị tách sang trang khác.",
                            block_id,
                        )
                else:
                    self.warn(
                        "caption_ambiguous",
                        "Chú thích chưa rõ đối tượng",
                        "Chưa tự liên kết khi không tìm được duy nhất một ảnh/bảng liền kề.",
                        block_id,
                    )
                continue
            decision = self.options.layout_decisions.get(block_id)
            if decision and decision != "keep":
                removed = self.ledger.trim_leading(node, block_id, permit_tabs=True)
                if removed:
                    self.log(
                        "whitespace",
                        block_id,
                        "reviewed_leading_layout",
                        removed,
                        decision=decision,
                    )
                override = (
                    {}
                    if decision == "body"
                    else {
                        "alignment": "center",
                        "left": self._available_width(block) // 2
                        if decision == "right_block"
                        else 0,
                        "right": 0,
                        "first": 0,
                    }
                )
                self.paragraph(node, block, "body", override=override)
                continue
            if decision == "keep":
                self.paragraph(
                    node,
                    block,
                    "body",
                    override={"alignment": block["alignment"] or "left"},
                    preserve_indent=True,
                )
                continue
            if block["role"] == "signature" or (
                block["alignment"] in {"center", "right", "end"}
                and len(block["text"]) < 160
            ):
                if (
                    self.options.mode == "layout"
                    and block["leading_layout"]
                    and block["role"] == "signature"
                ):
                    removed = self.ledger.trim_leading(node, block_id, permit_tabs=True)
                    if removed:
                        self.log("whitespace", block_id, "signature_layout", removed)
                        self.paragraph(
                            node,
                            block,
                            "body",
                            override={
                                "alignment": "center",
                                "left": 4800,
                                "right": 0,
                                "first": 0,
                            },
                        )
                continue
            role = (
                "reference"
                if block.get("region") == "references"
                else (
                    block["role"]
                    if block["role"]
                    in {"quote", "reference", "list", "manual_list", "lead_in"}
                    else "body"
                )
            )
            if block.get("region"):
                self.paragraph(node, block, role, preserve_indent=True)
                continue
            if block["leading_layout"] or block["has_tab"]:
                leading_count = len(text_of(node)) - len(text_of(node).lstrip(" "))
                ambiguous_short = leading_count >= 6 and len(block["text"]) < 100
                if self.options.mode == "strict" or block["has_tab"] or ambiguous_short:
                    self.warn(
                        "manual_layout",
                        "Giữ ký tự căn bố cục",
                        "Đoạn dùng khoảng trắng/Tab được giữ nguyên để tránh đoán sai. Chỉ tự xử lý khoảng trắng đầu thân bài trong chế độ chuẩn hóa.",
                        block_id,
                    )
                    self.paragraph(
                        node,
                        block,
                        role,
                        override={"alignment": block["alignment"] or "left"},
                        preserve_indent=True,
                    )
                    continue
                removed = self.ledger.trim_leading(node, block_id)
                if removed:
                    self.log("whitespace", block_id, "body_leading_spaces", removed)
            self.paragraph(node, block, role)
        if self.options.mode == "layout":
            self.empty_paragraphs()
        if self.layout_locked:
            # These operations can alter pagination, shared fields or objects
            # across a protected unit, even when its paragraph XML is unchanged.
            self.ledger.verify()
            return self
        from v1.enrich import captions, object_lists, structural_warnings

        sources = captions(self)
        if self.options.convert_manual_lists:
            from v1.list_fields import convert_lists

            convert_lists(self)
        if self.options.signature_position == "end_of_body":
            from v1.finishing import position_signature

            position_signature(self)
        if self.options.cover != "keep":
            from v1.fields import separate_cover

            separate_cover(self)
        if self.options.toc != "keep":
            from v1.fields import create_toc

            create_toc(self)
        if self.options.toc == "keep" and self.analysis.toc_region:
            from v1.fields import separate_existing_toc

            separate_existing_toc(self)
        object_lists(self, sources)
        if self.options.object_lists:
            from v1.finishing import glossary

            glossary(self)
        structural_warnings(self)
        if self.options.page_numbers == "arabic":
            from v1.fields import add_page_numbers

            add_page_numbers(self)
        elif self.options.page_numbers == "academic":
            from v1.academic import academic_sections

            academic_sections(self)
        self.ledger.verify()
        return self

    def _available_width(self, block):
        index = block.get("section")
        if index is None:
            return 9071
        section = self.analysis.section_nodes[index][1]
        size, margin = section.find(q("pgSz")), section.find(q("pgMar"))
        try:
            width = int(size.get(q("w"), "11906")) if size is not None else 11906
            left = int(margin.get(q("left"), "1701")) if margin is not None else 1701
            right = int(margin.get(q("right"), "1134")) if margin is not None else 1134
            gutter = int(margin.get(q("gutter"), "0")) if margin is not None else 0
            return max(720, width - left - right - gutter)
        except ValueError:
            raise DocumentError("Kích thước vùng in không hợp lệ.") from None

    def _available_height(self, block):
        index = block.get("section")
        if index is None:
            return 14570
        section = self.analysis.section_nodes[index][1]
        size, margin = section.find(q("pgSz")), section.find(q("pgMar"))
        try:
            height = int(size.get(q("h"), "16838")) if size is not None else 16838
            top = int(margin.get(q("top"), "1134")) if margin is not None else 1134
            bottom = (
                int(margin.get(q("bottom"), "1134")) if margin is not None else 1134
            )
            return max(720, height - top - bottom)
        except ValueError:
            raise DocumentError("Chiều cao vùng in không hợp lệ.") from None

    def table(self, table, block):
        if (
            block["position"] <= self.cover_position
            and self.options.cover != "keep"
            and not table.xpath(PROTECTED + " | .//w:tbl", namespaces=NS)
        ):
            self.prop(ensure(table, "tblPr"), "jc", {"val": "center"})
            self.prop(ensure(table, "tblPr"), "tblInd", {"w": 0, "type": "dxa"})
            if block.get("format_safe"):
                available = self._available_width(block)
                grid = table.findall("w:tblGrid/w:gridCol", NS)
                weights = [max(1, int(c.get(q("w"), "1"))) for c in grid]
                widths = [int(available * value / sum(weights)) for value in weights]
                widths[-1] += available - sum(widths)
                self.prop(
                    ensure(table, "tblPr"), "tblW", {"w": available, "type": "dxa"}
                )
                self.prop(ensure(table, "tblPr"), "tblLayout", {"type": "fixed"})
                for col, width in zip(grid, widths):
                    col.set(q("w"), str(width))
                for row in table.findall(q("tr")):
                    cursor = 0
                    for cell in row.findall(q("tc")):
                        span_node = cell.find("w:tcPr/w:gridSpan", NS)
                        span = (
                            int(span_node.get(q("val"))) if span_node is not None else 1
                        )
                        self.prop(
                            ensure(cell, "tcPr"),
                            "tcW",
                            {"w": sum(widths[cursor : cursor + span]), "type": "dxa"},
                        )
                        cursor += span
            for p in table.xpath("./w:tr/w:tc/w:p", namespaces=NS):
                self.cover(
                    p,
                    {
                        **block,
                        "text": plain(text_of(p)),
                        "role": "body",
                        "protected": False,
                        "cover_cell": True,
                    },
                )
            self.log("cover", block["id"], "cover_table_alignment")
            return
        if not block.get("format_safe", block["simple"]) or table.xpath(
            PROTECTED + " | .//w:drawing", namespaces=NS
        ):
            self.warn(
                "complex_table",
                "Bảng phức tạp được giữ nguyên",
                "Bảng lồng, lưới thiếu/không nhất quán hoặc có đối tượng đặc biệt; không tự đổi cấu trúc.",
                block["id"],
            )
            return
        # A borderless fixed-width table may be a layout form, not data.
        if block["position"] <= self.cover_position:
            self.warn(
                "cover_table",
                "Giữ bảng dựng bìa",
                "Không áp kiểu bảng dữ liệu vào vùng bìa.",
                block["id"],
            )
            return
        before = canonical(table)
        available = self._available_width(block)
        rows = table.findall(q("tr"))
        columns = block["columns"]
        weights = []
        for index in range(columns):
            samples = [
                len(plain(text_of(row.findall(q("tc"))[index])))
                for row in rows
                if len(row.findall(q("tc"))) == columns
            ]
            weights.append(
                max(5, min(45, (max(samples) if samples else 5) ** 0.65 * 3))
            )
        total = sum(weights)
        widths = [max(480, int(available * w / total)) for w in weights]
        if sum(widths) > available:
            self.warn(
                "table_too_many_columns",
                "Bảng quá dày so với vùng in",
                "Giữ độ rộng gốc; không thu nhỏ chữ hoặc ép cột quá hẹp.",
                block["id"],
            )
            return
        widths[-1] += available - sum(widths)
        props = ensure(table, "tblPr")
        self.prop(props, "tblW", {"w": available, "type": "dxa"})
        self.prop(props, "tblInd", {"w": 0, "type": "dxa"})
        self.prop(props, "jc", {"val": "center"})
        self.prop(props, "tblLayout", {"type": "fixed"})
        borders = ensure(props, "tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            self.prop(borders, edge, {"val": "single", "sz": 4, "color": "CDD6CD"})
        margins = ensure(props, "tblCellMar")
        for side in ("top", "bottom", "left", "right"):
            self.prop(
                margins,
                side,
                {"w": 80 if side in {"top", "bottom"} else 100, "type": "dxa"},
            )
        for col, width in zip(table.findall("w:tblGrid/w:gridCol", NS), widths):
            col.set(q("w"), str(width))
        header = block["header"] or block["id"] in self.options.table_headers
        compact = (
            len(rows) <= 6
            and sum(len(text_of(r)) for r in rows) < 800
            and all(len(text_of(c)) < 250 for r in rows for c in r.findall(q("tc")))
        )
        for ri, row in enumerate(rows):
            if header and ri == 0:
                self.prop(ensure(row, "trPr"), "tblHeader", {"val": 1})
            height = row.find("w:trPr/w:trHeight", NS)
            if height is not None and height.get(q("hRule")) == "exact":
                self.prop(ensure(row, "trPr"), "trHeight", {"hRule": "atLeast"})
            # Avoid forcing an oversized row to stay on a single page.
            if max(
                (len(text_of(c)) for c in row.findall(q("tc"))), default=0
            ) < 350 and not row.xpath(".//w:drawing | .//w:br", namespaces=NS):
                self.prop(ensure(row, "trPr"), "cantSplit", {"val": 1})
            cursor = 0
            for ci, cell in enumerate(row.findall(q("tc"))):
                cp = ensure(cell, "tcPr")
                span_node = cp.find(q("gridSpan"))
                span = int(span_node.get(q("val"))) if span_node is not None else 1
                self.prop(
                    cp, "tcW", {"w": sum(widths[cursor : cursor + span]), "type": "dxa"}
                )
                cursor += span
                self.prop(
                    cp, "vAlign", {"val": "center" if ri == 0 and header else "top"}
                )
                if header:
                    self.prop(
                        cp,
                        "shd",
                        {"val": "clear", "fill": "EAF0E8" if ri == 0 else "FFFFFF"},
                    )
                for p in cell.findall(q("p")):
                    numeric = bool(
                        re.fullmatch(r"[+\-]?\d[\d\s.,%/\-]*", plain(text_of(p)))
                    )
                    self.paragraph(
                        p,
                        {"id": block["id"]},
                        "table",
                        override={
                            "alignment": "right"
                            if numeric and not (ri == 0 and header)
                            else "left",
                            "keep_next": ri < len(rows) - 1
                            and (compact or ri == 0 and header or ri == len(rows) - 2),
                        },
                    )
                    if header and ri == 0:
                        for run in p.xpath("./w:r[w:t]", namespaces=NS):
                            self.prop(ensure(run, "rPr"), "b", {"val": 1})
        if canonical(table) != before:
            self.log("tables", block["id"], "simple_table_layout")
        if block["suggest_header"] and not header:
            self.warn(
                "table_header_review",
                "Hàng đầu có thể là tiêu đề",
                "Chưa bật lặp tiêu đề vì bạn chưa xác nhận hàng đầu.",
                block["id"],
            )

    def image(self, p, block):
        if p.xpath(
            ".//wp:anchor | .//w:pict | .//w:object", namespaces={**NS, "wp": WP}
        ):
            self.warn(
                "floating_image",
                "Ảnh nổi được giữ nguyên",
                "Không thay đổi neo ảnh hoặc cơ chế bọc chữ. Hãy xem lại trong Word.",
                block["id"],
            )
            return
        if plain(text_of(p)):
            self.warn(
                "mixed_image",
                "Ảnh nằm cùng văn bản",
                "Không tự căn giữa đoạn có cả chữ và ảnh.",
                block["id"],
            )
            return
        if len(p.xpath(".//wp:inline", namespaces={"wp": WP})) > 1:
            self.warn(
                "image_group",
                "Giữ nhóm nhiều ảnh trong một đoạn",
                "Không tự đổi kích thước hoặc cách xếp nhóm ảnh; hãy kiểm tra trong Word.",
                block["id"],
            )
            return
        before = canonical(p)
        max_cx = self._available_width(block) * 635
        max_cy = max(720, self._available_height(block) - 480) * 635
        for inline in p.xpath(".//wp:inline", namespaces={"wp": WP}):
            extent = inline.find(f"{{{WP}}}extent")
            if extent is None:
                continue
            try:
                cx, cy = int(extent.get("cx", "0")), int(extent.get("cy", "0"))
            except ValueError:
                self.warn(
                    "image_dimensions",
                    "Kích thước ảnh không hợp lệ",
                    "Giữ ảnh để bạn kiểm tra.",
                    block["id"],
                )
                continue
            self._image_aspect(inline, cx, cy, block)
            cover_image = block["position"] <= self.cover_position
            limit_x = max_cx * 0.3 if cover_image else max_cx
            limit_y = max_cy * 0.2 if cover_image else max_cy
            ratio = min(1, limit_x / cx, limit_y / cy) if cx > 0 and cy > 0 else 1
            if not cover_image and cx > 0 and cy > 0 and cx < max_cx * 0.65:
                pixels = self._raster_size(inline)
                if (
                    self.options.enlarge_images
                    and pixels
                    and pixels[0] >= 1000
                    and not inline.xpath(".//a:srcRect", namespaces={"a": A})
                    and not inline.xpath(
                        ".//a:xfrm[@rot and @rot!='0']", namespaces={"a": A}
                    )
                ):
                    ratio = min(
                        max_cx * 0.9 / cx, max_cy / cy, pixels[0] / 150 * 914400 / cx
                    )
                if ratio <= 1:
                    self.warn(
                        "image_small",
                        "Ảnh có thể quá nhỏ để đọc",
                        "Giữ ảnh nhỏ/cắt xén hoặc ảnh thiếu độ phân giải; hãy kiểm tra chữ trong hình, không phóng mờ tự động.",
                        block["id"],
                    )
            if cx > 0 and cy > 0 and abs(ratio - 1) > 0.001:
                nx, ny = int(cx * ratio), int(cy * ratio)
                extent.set("cx", str(nx))
                extent.set("cy", str(ny))
                for ext in inline.xpath(".//a:xfrm/a:ext", namespaces={"a": A}):
                    ext.set("cx", str(nx))
                    ext.set("cy", str(ny))
        props = ensure(p, "pPr")
        self.prop(props, "jc", {"val": "center"})
        if block["position"] <= self.cover_position and self.options.cover != "keep":
            self.prop(
                props,
                "ind",
                {"left": 0, "right": 0, "firstLine": 0},
                (
                    "hanging",
                    "firstLineChars",
                    "hangingChars",
                    "leftChars",
                    "rightChars",
                    "start",
                    "end",
                    "startChars",
                    "endChars",
                ),
            )
        self.prop(props, "spacing", {"before": 120, "after": 120})
        self.prop(props, "keepLines", {"val": 1})
        if canonical(p) != before:
            self.log("images", block["id"], "inline_image_layout")

    def _raster_size(self, inline):
        relname = "word/_rels/document.xml.rels"
        if relname not in self.package.parts:
            return None
        for blip in inline.xpath(".//a:blip", namespaces={"a": A}):
            rid = blip.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            )
            rel = next(
                (
                    r
                    for r in self.package.xml(relname)
                    if r.get("Id") == rid and r.get("TargetMode") != "External"
                ),
                None,
            )
            if rel is None:
                continue
            target = rel.get("Target", "")
            name = (
                target.lstrip("/")
                if target.startswith("/")
                else posixpath.normpath(posixpath.join("word", target))
            )
            raw = self.package.parts.get(name)
            if raw:
                try:
                    with Image.open(BytesIO(raw)) as image:
                        return image.size
                except (OSError, ValueError, Image.DecompressionBombError):
                    return None
        return None

    def _image_aspect(self, inline, cx, cy, block):
        if cx <= 0 or cy <= 0 or inline.xpath(".//a:srcRect", namespaces={"a": A}):
            return
        if any(
            int(n.get("rot", "0")) % 10800000
            for n in inline.xpath(".//a:xfrm[@rot]", namespaces={"a": A})
        ):
            return
        relname = "word/_rels/document.xml.rels"
        if relname not in self.package.parts:
            return
        relationships = self.package.xml(relname)
        for blip in inline.xpath(".//a:blip", namespaces={"a": A}):
            rid = blip.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            )
            rel = next(
                (
                    r
                    for r in relationships
                    if r.get("Id") == rid and r.get("TargetMode") != "External"
                ),
                None,
            )
            if rel is None:
                continue
            target = rel.get("Target", "")
            name = (
                target.lstrip("/")
                if target.startswith("/")
                else posixpath.normpath(posixpath.join("word", target))
            )
            raw = self.package.parts.get(name)
            if not raw:
                continue
            try:
                with Image.open(BytesIO(raw)) as image:
                    width, height = image.size
                if height > 0 and abs((cx / cy) / (width / height) - 1) > 0.05:
                    self.warn(
                        "image_aspect",
                        "Ảnh có thể đã bị kéo méo",
                        "Tỷ lệ hiển thị khác dữ liệu ảnh gốc. Hệ thống giữ tỷ lệ hiện tại; hãy kiểm tra trước khi quyết định khôi phục.",
                        block["id"],
                    )
            except (OSError, ValueError, Image.DecompressionBombError):
                continue

    def cover(self, p, block):
        if block["protected"] or block["role"] in {"image", "empty"}:
            if block["role"] == "image":
                self.image(p, block)
            elif block["protected"] and block["text"]:
                self.warn(
                    "cover_part_preserved",
                    "Giữ dòng bìa có cấu trúc đặc biệt",
                    "Dòng có trường tự động, công thức hoặc đối tượng được giữ nguyên định dạng; các dòng văn bản độc lập khác vẫn được căn giữa.",
                    block["id"],
                )
            return
        text = folded(block["text"])
        title = (
            bool(TITLE.match(text))
            and len(text) < 110
            and not text.endswith((".", "…"))
        )
        first_positions = [
            b["position"]
            for b in self.analysis.blocks
            if b["position"] <= self.cover_position
            and b["type"] == "paragraph"
            and b["text"]
        ]
        at_top = bool(first_positions) and block["position"] in first_positions[:2]
        date = (
            bool(re.search(r"(?:ha noi|ho chi minh|thang|nam)\b", text))
            and len(text) < 90
            and block["position"] == max(first_positions, default=-1)
        )
        cover_lines = sum(
            max(1, (len(b["text"]) + 59) // 60)
            for b in self.analysis.blocks
            if b["position"] <= self.cover_position and b["text"]
        )
        scale = min(
            1.0, self._available_height(block) / max(1, cover_lines * 420 + 3200)
        )
        spec = {
            "alignment": "center",
            "size": 40 if title else (28 if at_top else self.design.size),
            "before": int(self._available_height(block) * 0.08 * scale)
            if title
            else (int(600 * scale) if date else 160),
            "after": 360 if title else 160,
            "bold": title or at_top,
            "color": self.design.accent,
        }
        if self.options.cover == "minimal" and title:
            spec.update(
                size=44,
                before=int(self._available_height(block) * 0.1 * scale),
                after=360,
            )
        if re.match(r"^(de tai|topic|title)\b", text):
            spec.update(size=30, bold=True, before=320, after=240)
        if self.options.cover == "academic" and re.search(
            r"giang vien|sinh vien|ma so|ma lop|nhom", text
        ):
            spec.update(alignment="center", left=0, before=200)
        if len(text.split()) > 20 or text.endswith((".", "…")):
            spec.update(size=22, bold=False, before=120, after=120, color="59645F")
        if block.get("cover_cell"):
            spec.update(size=min(spec["size"], 24), before=40, after=40, line=260)
        if self.options.mode == "layout":
            removed = self.ledger.trim_cover_edges(p, block["id"])
            if removed:
                self.log("whitespace", block["id"], "cover_line_edges", removed)
        self.paragraph(p, block, "cover", override=spec)
        self.prop(ensure(p, "pPr"), "outlineLvl", {"val": 9})

    def empty_paragraphs(self):
        # Only collapse empty runs directly before a confirmed chapter heading.
        for heading in self.heading_blocks:
            if heading["level"] != 1:
                continue
            p = self.analysis.elements[heading["id"]]
            previous = p.getprevious()
            candidates = []
            while (
                previous is not None
                and previous.tag == q("p")
                and not text_of(previous)
            ):
                candidates.append(previous)
                previous = previous.getprevious()
            if len(candidates) < 2:
                continue
            removed = 0
            for candidate in candidates:
                block_id = next(
                    (
                        bid
                        for bid, element in self.analysis.elements.items()
                        if element is candidate
                    ),
                    None,
                )
                if (
                    not block_id
                    or block_id in self.locked
                    or not self.ledger.remove_empty(candidate, block_id)
                ):
                    break
                removed += 1
            if removed:
                self.prop(ensure(p, "pPr"), "pageBreakBefore", {"val": 1})
                self.log(
                    "empty_paragraphs", heading["id"], "chapter_page_break", removed
                )

    def serialize(self):
        return self.source_data if self.preserve_only else self.package.serialize()

    def report(self):
        counts = Counter()
        for event in self.changes:
            counts[event["rule"]] += (
                1
                if event["rule"] not in {"whitespace", "empty_paragraphs"}
                else event["count"]
            )
        return {
            "profile": self.options.profile,
            "mode": self.options.mode,
            "layout_policy": self.analysis.layout_policy,
            "operation_mode": "preserve_only"
            if self.preserve_only
            else "selective"
            if self.layout_locked
            else "format",
            "changes": [
                {"code": code, "title": LABELS[code], "count": count}
                for code, count in counts.items()
            ],
            "audit": self.changes,
            "warnings": self.warnings,
            "summary": {
                **self.analysis.public()["summary"],
                "changed_items": sum(counts.values()),
                "locked_blocks": len(self.locked),
            },
            "integrity": self.ledger.verify(),
            "scope": "Chuẩn hóa theo mẫu trong phạm vi được hỗ trợ; không phải chứng nhận đạt mọi quy chuẩn.",
        }
