"""Role-aware formatting. Every destructive operation has explicit consent."""

from collections import Counter
import re
import posixpath
from io import BytesIO
from PIL import Image
from core.autofix import SYMBOL_FONTS
from core.processor import DocumentError
from core.xmlutils import NS, q
from v1.analysis import Analysis, PROTECTED, folded, on, plain, text_of
from v1.design import Design, ensure
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
        self.package = Package(data)
        self.analysis = Analysis(self.package)
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
        self.design = Design(self.options.profile, self.package, self.ledger)

    def _validate(self):
        blocks = {b["id"]: b for b in self.analysis.blocks}
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
                or not blocks[block_id]["simple"]
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
        end = self.options.cover_end or self.analysis.cover_end
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
        locked = set(self.options.locked_blocks)
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
            if run.find("w:rPr/w:rStyle", NS) is not None:
                continue
            fonts = run.find("w:rPr/w:rFonts", NS)
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
        return changed

    def paragraph(self, p, block, role="body", level=0, override=None):
        if p.xpath(PROTECTED, namespaces=NS):
            return False
        spec = self.design.spec(role, level)
        spec.update(override or {})
        changed = self._fonts(
            p, spec, role in {"heading", "cover"} and spec.get("bold", False)
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
        if role != "list" and (
            role != "body"
            or props.find(q("ind")) is None
            or self.options.mode == "layout"
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
                ),
            )
        if role == "heading":
            changed |= self.prop(props, "outlineLvl", {"val": level - 1})
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
        blocked_sections = {
            b.get("section") for b in self.analysis.blocks if b["id"] in self.locked
        }
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
                self.heading_blocks.append({**block, "level": level})
                continue
            if block["role"] in {"heading", "emphasis"}:
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
                    if block["role"] in {"quote", "reference", "list", "manual_list"}
                    else "body"
                )
            )
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
                    continue
                removed = self.ledger.trim_leading(node, block_id)
                if removed:
                    self.log("whitespace", block_id, "body_leading_spaces", removed)
            self.paragraph(node, block, role)
        if self.options.mode == "layout":
            self.empty_paragraphs()
        if self.options.toc != "keep":
            from v1.fields import create_toc

            create_toc(self)
        if self.options.page_numbers == "arabic":
            from v1.fields import add_page_numbers

            add_page_numbers(self)
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
        if not block["simple"] or table.xpath(PROTECTED, namespaces=NS):
            self.warn(
                "complex_table",
                "Bảng phức tạp được giữ nguyên",
                "Bảng có ô gộp, bảng lồng hoặc đối tượng đặc biệt; chưa tự co hoặc đổi cấu trúc.",
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
            for ci, cell in enumerate(row.findall(q("tc"))):
                cp = ensure(cell, "tcPr")
                self.prop(cp, "tcW", {"w": widths[ci], "type": "dxa"})
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
                            else "left"
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
            if cx > 0 and cy > 0 and (cx > max_cx or cy > max_cy):
                ratio = min(1, max_cx / cx, max_cy / cy)
                nx, ny = int(cx * ratio), int(cy * ratio)
                extent.set("cx", str(nx))
                extent.set("cy", str(ny))
                for ext in inline.xpath(".//a:xfrm/a:ext", namespaces={"a": A}):
                    ext.set("cx", str(nx))
                    ext.set("cy", str(ny))
        props = ensure(p, "pPr")
        self.prop(props, "jc", {"val": "center"})
        self.prop(props, "spacing", {"before": 120, "after": 120})
        self.prop(props, "keepLines", {"val": 1})
        if canonical(p) != before:
            self.log("images", block["id"], "inline_image_layout")

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
            return
        text = folded(block["text"])
        title = (
            bool(re.search(r"bao cao|tieu luan|do an|luan van", text))
            and len(text) < 160
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
        spec = {
            "alignment": "center" if self.options.cover == "academic" else "left",
            "size": 40 if title else (28 if at_top else self.design.size),
            "before": 1080 if title else (720 if date else 160),
            "after": 360 if title else 160,
            "bold": title or at_top,
            "color": self.design.accent,
        }
        if self.options.cover == "minimal" and title:
            spec.update(size=48, before=1440, after=480)
        if self.options.cover == "academic" and re.search(
            r"giang vien|sinh vien|ma so|ma lop|nhom", text
        ):
            spec.update(alignment="left", left=1440, before=200)
        if self.options.mode == "layout":
            removed = self.ledger.trim_leading(p, block["id"], permit_tabs=True)
            if removed:
                self.log("whitespace", block["id"], "cover_leading_layout", removed)
        self.paragraph(p, block, "cover", override=spec)

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
