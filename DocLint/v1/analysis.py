"""Deterministic, explainable classification. Suggestions are not probabilities."""

from collections import Counter
import re
import unicodedata
from core.xmlutils import NS, q
from v1.package import Package


def plain(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def folded(text):
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def text_of(node):
    return "".join(node.xpath(".//w:t/text()", namespaces=NS))


def on(node):
    return node is not None and node.get(q("val"), "1").lower() not in {
        "0",
        "false",
        "off",
    }


class StyleResolver:
    def __init__(self, root):
        self.styles = {s.get(q("styleId")): s for s in root.findall(q("style"))}

    def chain(self, style_id):
        seen = set()
        while style_id and style_id not in seen:
            seen.add(style_id)
            style = self.styles.get(style_id)
            if style is None:
                break
            yield style
            based = style.find(q("basedOn"))
            style_id = based.get(q("val")) if based is not None else None

    def property(self, p, path, default=None):
        direct = p.find(path, NS)
        if direct is not None:
            return direct
        sid = p.find("w:pPr/w:pStyle", NS)
        for style in self.chain(sid.get(q("val")) if sid is not None else "Normal"):
            value = style.find(path, NS)
            if value is not None:
                return value
        return default

    def description(self, p):
        sid = p.find("w:pPr/w:pStyle", NS)
        style_id = sid.get(q("val")) if sid is not None else "Normal"
        names = [style_id]
        for style in self.chain(style_id):
            names.extend(style.xpath("./w:name/@w:val", namespaces=NS))
        return " ".join(names)

    def heading(self, p):
        outline = self.property(p, "w:pPr/w:outlineLvl")
        if outline is not None and outline.get(q("val"), "").isdigit():
            level = int(outline.get(q("val")))
            if 0 <= level < 6:
                return level + 1
        match = re.search(
            r"(?:heading|doclintheading|tieu de)\s*([1-6])\b",
            folded(self.description(p)),
        )
        return int(match.group(1)) if match else None

    def bold(self, run, p):
        direct = run.find("w:rPr/w:b", NS)
        if direct is not None:
            return on(direct)
        return on(self.property(p, "w:rPr/w:b"))

    def size(self, run, p):
        prop = run.find("w:rPr/w:sz", NS)
        if prop is None:
            prop = self.property(p, "w:rPr/w:sz")
        try:
            return int(prop.get(q("val"))) if prop is not None else None
        except (TypeError, ValueError):
            return None


CHAPTER = re.compile(r"^(?:chuong|chapter|phan|part)\s+(?:\d+|[ivxlcdm]+)\b", re.I)
DECIMAL = re.compile(r"^(\d+(?:\.\d+){1,5})\.?\s+\S")
SINGLE = re.compile(r"^(\d+)[.)]\s+\S")
BULLET = re.compile(r"^(?:[-•▪●]|[a-z][.)]|\d+[.)])\s+")
CAPTION = re.compile(r"^(hinh|figure|bang|table)\s+\d+(?:[.\-]\d+)*(?:[.:\s]|$)", re.I)
REF_HEADING = re.compile(r"^(tai lieu tham khao|references|bibliography)\s*$", re.I)
APP_HEADING = re.compile(r"^(phu luc|appendix|appendices)(?:\s|$)", re.I)
SIGNATURE = re.compile(
    r"(?:sinh vien thuc hien|nguoi thuc hien|nguoi lap|nguoi viet|nguoi huong dan|ngay\s+\d+\s+thang)",
    re.I,
)
PROTECTED = ".//m:oMath | .//m:oMathPara | .//w:fldChar | .//w:instrText | .//w:fldSimple | .//w:object | .//w:pict | .//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo | .//w:sdt"


class Analysis:
    def __init__(self, package):
        self.package = package
        self.body = package.document.find(q("body"))
        self.resolver = StyleResolver(package.styles)
        self.elements = {}
        self.blocks = []
        self.toc_nodes = []
        self.toc_region = None
        self.sections = []
        self._build()

    def _build(self):
        direct = list(self.body)
        paragraph_counter = table_counter = 0
        for position, element in enumerate(direct):
            if element.tag == q("p"):
                paragraph_counter += 1
                block_id = f"p{paragraph_counter:05}"
                text = text_of(element)
                display = plain(text)
                style_name = folded(self.resolver.description(element))
                runs = element.xpath(".//w:r[w:t]", namespaces=NS)
                bold = bool(runs) and all(self.resolver.bold(r, element) for r in runs)
                sizes = [self.resolver.size(r, element) for r in runs]
                sizes = [n for n in sizes if n]
                level = self.resolver.heading(element)
                alignment = self.resolver.property(element, "w:pPr/w:jc")
                align = alignment.get(q("val")) if alignment is not None else None
                role, certainty, reason = "body", "certain", "Đoạn văn thông thường."
                if not display:
                    role, reason = (
                        "empty",
                        "Đoạn không có văn bản; kiểm tra cấu trúc trước khi xóa.",
                    )
                if element.xpath(PROTECTED, namespaces=NS):
                    role, reason = (
                        "protected",
                        "Chứa trường tự động, công thức, revision hoặc đối tượng cần bảo vệ.",
                    )
                elif re.search(r"code|source|preformatted|verbatim", style_name) or any(
                    (v or "").lower() in {"consolas", "courier new", "monospace"}
                    for v in element.xpath(".//w:rFonts/@w:ascii", namespaces=NS)
                ):
                    role, reason = (
                        "code",
                        "Kiểu mã nguồn hoặc phông đơn cách; giữ nguyên khoảng trắng.",
                    )
                elif level:
                    role, reason = "heading", "Heading/outline đã có trong tài liệu."
                elif "toc" in style_name or "muc luc" in style_name:
                    role, reason = "toc", "Kiểu mục lục có sẵn."
                elif CAPTION.match(folded(display)) or re.search(
                    r"caption|chu thich", style_name
                ):
                    role, certainty, reason = (
                        "caption",
                        "suggested",
                        "Tiền tố chú thích và vị trí cần được đối chiếu với đối tượng.",
                    )
                elif element.xpath(".//w:drawing", namespaces=NS):
                    role, reason = (
                        "image",
                        "Đoạn chứa hình; không đổi nội dung hoặc cơ chế bọc chữ.",
                    )
                elif self.resolver.property(element, "w:pPr/w:numPr") is not None:
                    role, reason = "list", "Danh sách Word có cấu trúc."
                elif re.search(r"quote|citation|trich dan", style_name):
                    role, reason = "quote", "Kiểu đoạn trích dẫn."
                elif "reference" in style_name or "bibliography" in style_name:
                    role, reason = "reference", "Kiểu tài liệu tham khảo."
                elif REF_HEADING.match(folded(display)) or APP_HEADING.match(
                    folded(display)
                ):
                    role, level, certainty, reason = (
                        "heading",
                        1,
                        "suggested",
                        "Tên phần đặc biệt; cần xác nhận trước khi gán Heading.",
                    )
                elif CHAPTER.match(folded(display)) and len(display) < 180:
                    role, level, certainty, reason = (
                        "heading",
                        1,
                        "suggested",
                        "Có nhãn chương/phần; cần xác nhận.",
                    )
                elif (match := DECIMAL.match(display)) and len(display) < 160:
                    role, level, certainty, reason = (
                        "heading",
                        min(6, match.group(1).count(".") + 1),
                        "suggested",
                        "Số đề mục nhiều cấp; kiểm tra cùng cây đề mục.",
                    )
                elif SINGLE.match(display) and bold and len(display) < 120:
                    role, level, certainty, reason = (
                        "heading",
                        1,
                        "suggested",
                        "Có thể là tiêu đề hoặc mục danh sách; cần duyệt.",
                    )
                elif BULLET.match(display):
                    role, reason = (
                        "manual_list",
                        "Danh sách gõ tay; chỉ chỉnh thụt treo, không đổi tiền tố.",
                    )
                elif SIGNATURE.search(folded(display)) and len(display) < 140:
                    role, reason = (
                        "signature",
                        "Khối chữ ký/ngày tháng; cần giữ ý đồ trình bày.",
                    )
                elif bold and len(display) < 100:
                    role, certainty, reason = (
                        "emphasis",
                        "suggested",
                        "Đoạn ngắn in đậm; chưa đủ căn cứ coi là tiêu đề.",
                    )
                item = {
                    "id": block_id,
                    "type": "paragraph",
                    "position": position,
                    "role": role,
                    "certainty": certainty,
                    "reason": reason,
                    "text": display[:300],
                    "level": level,
                    "alignment": align,
                    "bold": bold,
                    "font_size": max(sizes) / 2 if sizes else None,
                    "leading_layout": bool(
                        text.startswith(" ")
                        or element.xpath("./w:r[1]/w:tab", namespaces=NS)
                    ),
                    "has_tab": bool(element.xpath(".//w:tab", namespaces=NS)),
                    "protected": role in {"protected", "code"},
                }
            elif element.tag == q("tbl"):
                table_counter += 1
                block_id = f"t{table_counter:05}"
                rows = element.findall(q("tr"))
                columns = len(element.findall("w:tblGrid/w:gridCol", NS))
                merged = bool(
                    element.xpath(
                        ".//w:gridSpan | .//w:vMerge | .//w:hMerge", namespaces=NS
                    )
                )
                nested = bool(element.xpath(".//w:tbl", namespaces=NS))
                first = rows[0] if rows else None
                header = first is not None and on(first.find("w:trPr/w:tblHeader", NS))
                texts = (
                    first.xpath(".//w:r[w:t]", namespaces=NS)
                    if first is not None
                    else []
                )
                guess_header = bool(texts) and all(
                    on(r.find("w:rPr/w:b", NS)) for r in texts
                )
                item = {
                    "id": block_id,
                    "type": "table",
                    "role": "table",
                    "position": position,
                    "text": plain(text_of(element))[:160],
                    "rows": len(rows),
                    "columns": columns,
                    "simple": bool(rows)
                    and 0 < columns <= 10
                    and not merged
                    and not nested,
                    "header": header,
                    "suggest_header": guess_header and not header,
                    "certainty": "certain",
                    "protected": merged or nested,
                    "reason": "Bảng đơn giản."
                    if not merged and not nested
                    else "Bảng gộp ô/lồng nhau; bảo vệ cấu trúc.",
                }
            elif element.tag == q("sdt"):
                block_id = f"x{position:05}"
                item = {
                    "id": block_id,
                    "type": "container",
                    "role": "protected",
                    "position": position,
                    "text": plain(text_of(element))[:160],
                    "protected": True,
                    "certainty": "certain",
                    "reason": "Content control; giữ nguyên trừ khi thay mục lục được xác nhận.",
                }
            else:
                continue
            self.elements[block_id] = element
            self.blocks.append(item)
        if len(self.blocks) > 5000:
            from core.processor import DocumentError

            raise DocumentError(
                "V1 chỉ hỗ trợ tối đa 5.000 khối trực tiếp; hãy chia nhỏ tài liệu."
            )
        sizes = Counter(
            b["font_size"]
            for b in self.blocks
            if b["role"] == "body" and b.get("font_size")
        )
        common_size = sizes.most_common(1)[0][0] if sizes else 13
        for block in self.blocks:
            if block["role"] == "body" and 3 < len(block["text"]) < 160:
                letters = [c for c in block["text"] if c.isalpha()]
                uppercase = (
                    len(letters) > 4
                    and sum(c.isupper() for c in letters) / len(letters) > 0.9
                )
                larger = (
                    block.get("font_size") is not None
                    and block["font_size"] >= common_size + 2
                )
                if (larger or uppercase) and len(block["text"].split()) < 25:
                    block.update(
                        role="emphasis",
                        certainty="suggested",
                        reason="Đoạn nổi bật về cỡ chữ/chữ hoa; cần bạn xác nhận vai trò.",
                    )
        # Scope each block to the section that ends at the following sectPr.
        section_nodes = []
        for position, element in enumerate(direct):
            section = (
                element.find("w:pPr/w:sectPr", NS)
                if element.tag == q("p")
                else (element if element.tag == q("sectPr") else None)
            )
            if section is not None:
                size, cols = section.find(q("pgSz")), section.find(q("cols"))
                try:
                    landscape = size is not None and (
                        size.get(q("orient")) == "landscape"
                        or int(size.get(q("w"), "0")) > int(size.get(q("h"), "99999"))
                    )
                    multicolumn = cols is not None and (
                        int(cols.get(q("num"), "1")) > 1 or len(cols) > 0
                    )
                except ValueError:
                    from core.processor import DocumentError

                    raise DocumentError("Thông số section không hợp lệ.") from None
                section_nodes.append((position, section))
                self.sections.append(
                    {
                        "id": f"s{len(section_nodes)}",
                        "position": position,
                        "complex": bool(landscape or multicolumn),
                    }
                )
        self.section_nodes = section_nodes
        for block in self.blocks:
            index = next(
                (
                    i
                    for i, (position, _) in enumerate(section_nodes)
                    if block["position"] <= position
                ),
                None,
            )
            block["section"] = index
            if index is not None and self.sections[index]["complex"]:
                block["complex_section"] = True
        # Protected references/appendices extend from their headings to the next
        # top-level heading of another region; appendix extends to the end.
        region = None
        for block in self.blocks:
            txt = folded(block["text"])
            if block["type"] == "paragraph" and REF_HEADING.match(txt):
                region = "references"
            elif block["type"] == "paragraph" and APP_HEADING.match(txt):
                region = "appendices"
            elif (
                region == "references"
                and block["role"] == "heading"
                and block.get("level") == 1
            ):
                region = None
            block["region"] = region
        self._toc()
        self.cover_end = None
        # A cover proposal needs evidence and an explicit boundary, never just
        # "everything before first heading" in an arbitrary document.
        first = self.blocks[:35]
        evidence = any(
            re.search(r"dai hoc|truong|bao cao|tieu luan|do an", folded(b["text"]))
            for b in first[:12]
        )
        if evidence:
            for block in first:
                node = self.elements[block["id"]]
                boundary = (
                    block["role"] == "heading"
                    or plain(block["text"]).upper() == "MỤC LỤC"
                    or bool(self.toc_region and block["id"] == self.toc_region["start"])
                )
                if boundary and block["position"] > 2:
                    previous = [
                        b for b in self.blocks if b["position"] < block["position"]
                    ]
                    self.cover_end = previous[-1]["id"] if previous else None
                    break
                if node.tag == q("p") and (
                    node.find("w:pPr/w:sectPr", NS) is not None
                    or node.xpath('./w:r/w:br[@w:type="page"]', namespaces=NS)
                ):
                    self.cover_end = block["id"]
                    break
        # Associate captions only with adjacent objects, allowing empty paragraphs.
        nonempty = [b for b in self.blocks if b["role"] != "empty"]
        for index, block in enumerate(nonempty):
            if block["role"] != "caption":
                continue
            is_table = folded(block["text"]).startswith(("bang", "table"))
            neighbors = (
                nonempty[max(0, index - 1) : index] + nonempty[index + 1 : index + 2]
            )
            named = CAPTION.match(folded(block["text"]))
            targets = (
                [
                    b
                    for b in neighbors
                    if b["role"] == ("table" if is_table else "image")
                ]
                if named
                else [b for b in neighbors if b["role"] in {"table", "image"}]
            )
            block["targets"] = [b["id"] for b in targets]
            block["target"] = targets[0]["id"] if len(targets) == 1 else None
            block["certainty"] = "certain" if len(targets) == 1 else "suggested"

    def _toc(self):
        for block in self.blocks:
            node = self.elements[block["id"]]
            if node.tag == q("sdt") and (
                node.xpath(
                    './w:sdtPr/w:docPartObj/w:docPartGallery[contains(@w:val,"Table of Contents")]',
                    namespaces=NS,
                )
                or node.xpath('./w:sdtPr/w:tag[@w:val="DocLintTOC"]', namespaces=NS)
                or any(
                    "TOC " in (s or "")
                    for s in node.xpath(".//w:instrText/text()", namespaces=NS)
                )
            ):
                self.toc_nodes = [node]
                self.toc_region = {
                    "start": block["id"],
                    "end": block["id"],
                    "kind": "field",
                }
                return
        for index, block in enumerate(self.blocks):
            if plain(block["text"]).upper() not in {
                "MỤC LỤC",
                "TABLE OF CONTENTS",
                "CONTENTS",
            }:
                continue
            selected = [block]
            remaining = self.blocks[index + 1 :]
            for offset, following in enumerate(remaining):
                text = following["text"]
                is_entry = following["role"] == "toc" or bool(
                    re.search(
                        r"(?:\.{2,}|\t|\s{2,})\s*\d+\s*$",
                        text_of(self.elements[following["id"]]),
                    )
                )
                repeated = bool(text) and any(
                    plain(b["text"]) == plain(text) for b in remaining[offset + 1 :]
                )
                if following["role"] == "empty" or is_entry or repeated:
                    selected.append(following)
                else:
                    break
            if len(selected) > 1:
                self.toc_nodes = [self.elements[b["id"]] for b in selected]
                for entry in selected:
                    entry["role"] = "toc"
                self.toc_region = {
                    "start": selected[0]["id"],
                    "end": selected[-1]["id"],
                    "kind": "manual",
                }
                return

    def public(self):
        counts = Counter(b["role"] for b in self.blocks)
        return {
            "blocks": self.blocks,
            "counts": dict(counts),
            "sections": self.sections,
            "cover_end": self.cover_end,
            "toc_region": self.toc_region,
            "summary": {
                "paragraphs": len(self.package.document.xpath(".//w:p", namespaces=NS)),
                "tables": len(self.package.document.xpath(".//w:tbl", namespaces=NS)),
                "images": len(
                    self.package.document.xpath(
                        ".//w:drawing | .//w:pict", namespaces=NS
                    )
                ),
                "equations": len(
                    self.package.document.xpath(".//m:oMath", namespaces=NS)
                ),
            },
            "limitations": [
                "V1 ưu tiên báo cáo học thuật một cột.",
                "Suy luận theo quy tắc; các đề xuất tiêu đề cần bạn duyệt.",
                "Vùng khóa giữ nguyên; section dùng chung có thể được giữ để bảo vệ bố cục.",
            ],
        }


def analyze_document(data):
    return Analysis(Package(data)).public()
