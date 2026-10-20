"""Preserve an OPC package; track authorized content edits separately from formatting."""

from copy import copy, deepcopy
from io import BytesIO
import hashlib
import re
import zipfile
from lxml import etree
from core.processor import _open, DocumentError
from core.xmlutils import NS, q, parse_xml

WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


class Package:
    def __init__(self, data):
        archive, document, styles = _open(data)
        with archive:
            self.infos = [copy(i) for i in archive.infolist()]
            self.parts = {
                i.filename: archive.read(i.filename) for i in archive.infolist()
            }
            self.comment = archive.comment
        self.roots = {"word/document.xml": document, "word/styles.xml": styles}
        self.source_hash = hashlib.sha256(data).hexdigest()
        self.write_roots = set(self.roots)

    @property
    def document(self):
        return self.roots["word/document.xml"]

    @property
    def styles(self):
        return self.roots["word/styles.xml"]

    def xml(self, name):
        if name not in self.roots:
            self.roots[name] = parse_xml(self.parts[name])
        return self.roots[name]

    def serialize(self):
        parts = dict(self.parts)
        parts.update(
            {
                name: etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True
                )
                for name, root in self.roots.items()
                if name in self.write_roots
            }
        )
        target = BytesIO()
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.comment = self.comment
            known = set()
            for info in self.infos:
                archive.writestr(copy(info), parts[info.filename])
                known.add(info.filename)
            for name, value in parts.items():
                if name not in known:
                    archive.writestr(name, value)
        return target.getvalue()


def canonical(node):
    return etree.tostring(node, method="c14n", exclusive=True, with_comments=True)


# Only formatting properties may be ignored by the independent structural gate.
FORMAT_PROPERTIES = {
    q("pPr"): {
        "pStyle",
        "jc",
        "spacing",
        "ind",
        "widowControl",
        "keepNext",
        "keepLines",
        "pageBreakBefore",
        "outlineLvl",
        "tabs",
        "contextualSpacing",
        "snapToGrid",
        "pBdr",
        "shd",
    },
    q("rPr"): {"rFonts", "sz", "szCs", "b", "bCs", "i", "iCs", "color"},
    q("sectPr"): {"pgMar", "pgSz", "pgNumType", "titlePg", "vAlign", "pgBorders"},
    q("tblPr"): {
        "tblW",
        "tblInd",
        "tblLayout",
        "tblBorders",
        "tblCellMar",
        "jc",
        "tblLook",
    },
    q("tcPr"): {"tcW", "tcMar", "shd", "vAlign", "noWrap", "tcFitText"},
    q("trPr"): {"tblHeader", "cantSplit", "trHeight"},
}
CONTAINERS = {q(n) for n in ("pPr", "rPr", "tblPr", "tcPr", "trPr")}


def structural_signature(root):
    root = deepcopy(root)
    for node in list(root.iter())[::-1]:
        parent = node.getparent()
        if parent is None or not isinstance(node.tag, str):
            continue
        if node.tag in {q(n) for n in FORMAT_PROPERTIES.get(parent.tag, set())}:
            # A property cannot be used to conceal document content.
            if (
                node.xpath(
                    ".//w:t | .//w:drawing | .//m:oMath | .//w:object", namespaces=NS
                )
                or (node.text or "").strip()
            ):
                raise DocumentError(
                    "Thuộc tính trình bày chứa cấu trúc nội dung không hợp lệ."
                )
            parent.remove(node)
        elif (
            node.tag in CONTAINERS
            and not len(node)
            and not node.attrib
            and not (node.text or "").strip()
        ):
            parent.remove(node)
        elif node.tag == q("gridCol") and parent.tag == q("tblGrid"):
            node.attrib.pop(q("w"), None)
        elif node.tag == f"{{{WP}}}extent" or (
            node.tag == f"{{{A}}}ext" and parent.tag == f"{{{A}}}xfrm"
        ):
            node.attrib.pop("cx", None)
            node.attrib.pop("cy", None)

    def token(node):
        if not isinstance(node.tag, str):
            return ("comment", node.text)
        text = node.text or None
        if len(node) and text and not text.strip():
            text = None
        return (
            node.tag,
            tuple(sorted(node.attrib.items())),
            text,
            node.tail if (node.tail or "").strip() else None,
            tuple(token(c) for c in node),
        )

    return token(root)


class IntegrityLedger:
    """Expected content is advanced only by narrowly authorized operations.

    Formatting does not alter this snapshot. Exact originals are retained in the
    input package; protected subtrees also receive a strict formatting lock.
    """

    def __init__(self, package):
        self.package = package
        self.original_parts = dict(package.parts)
        self.expected = {}
        self.pairs = {}
        self.events = []
        self.locks = []
        self.generated = set()
        self._paragraph_refs_ready = False
        self._paragraph_refs = None
        self.track("word/document.xml")
        self.track("word/styles.xml")

    def track(self, name):
        root = self.package.xml(name)
        self.package.write_roots.add(name)
        if name not in self.expected:
            expected = deepcopy(root)
            self.expected[name] = expected
            self.pairs.update(zip(root.iter(), expected.iter()))
        return root

    def lock(self, node, block_id):
        self.locks.append((node, canonical(node), block_id))

    def append_generated(self, parent, node, reason, index=None):
        if (
            parent not in self.pairs
            and parent.tag in FORMAT_PROPERTIES
            and all(
                child.tag in {q(n) for n in FORMAT_PROPERTIES[parent.tag]}
                for child in parent
            )
        ):
            expected_owner = self.pairs[parent.getparent()]
            clone = deepcopy(parent)
            expected_owner.insert(list(parent.getparent()).index(parent), clone)
            self.pairs.update(zip(parent.iter(), clone.iter()))
        expected_parent = self.pairs[parent]
        if index is None:
            index = len(parent)
        clone = deepcopy(node)
        parent.insert(index, node)
        expected_parent.insert(index, clone)
        self.pairs.update(zip(node.iter(), clone.iter()))
        self.generated.update(node.iter())
        self.events.append(
            {"rule": reason, "operation": "generated_structure", "count": 1}
        )

    def new_part(self, name, root, reason):
        if name in self.original_parts or name in self.expected:
            raise DocumentError("Không được ghi đè thành phần gốc khi tạo phần mới.")
        self.package.roots[name] = root
        self.package.write_roots.add(name)
        clone = deepcopy(root)
        self.expected[name] = clone
        self.pairs.update(zip(root.iter(), clone.iter()))
        self.generated.update(root.iter())
        self.events.append(
            {"rule": reason, "operation": "generated_part", "part": name, "count": 1}
        )

    def trim_leading(self, paragraph, block_id, permit_tabs=False):
        # Never touch content in fields, revisions, drawings, equations, or links.
        if paragraph.xpath(
            ".//w:fldChar | .//w:instrText | .//w:fldSimple | .//w:ins | .//w:del | .//m:oMath | .//w:drawing | .//w:hyperlink",
            namespaces=NS,
        ):
            return 0
        removed = 0
        for run in paragraph.findall(q("r")):
            for node in list(run):
                if node.tag == q("rPr"):
                    continue
                if node.tag == q("tab") and permit_tabs:
                    expected = self.pairs[node]
                    expected.getparent().remove(expected)
                    run.remove(node)
                    removed += 1
                elif node.tag == q("t"):
                    before = node.text or ""
                    # Deliberately excludes NBSP and all whitespace inside content.
                    after = before.lstrip(" ")
                    if before != after:
                        if before[: len(before) - len(after)].strip(" "):
                            raise DocumentError(
                                "Phép làm sạch khoảng trắng không hợp lệ."
                            )
                        self.pairs[node].text = after
                        node.text = after
                        removed += len(before) - len(after)
                    if after:
                        if removed:
                            self.events.append(
                                {
                                    "rule": "leading_layout",
                                    "operation": "authorized_whitespace",
                                    "block_id": block_id,
                                    "count": removed,
                                }
                            )
                        return removed
                else:
                    if removed:
                        self.events.append(
                            {
                                "rule": "leading_layout",
                                "operation": "authorized_whitespace",
                                "block_id": block_id,
                                "count": removed,
                            }
                        )
                    return removed
        if removed:
            self.events.append(
                {
                    "rule": "leading_layout",
                    "operation": "authorized_whitespace",
                    "block_id": block_id,
                    "count": removed,
                }
            )
        return removed

    def _empty_metadata_safe(self, paragraph):
        w14 = "http://schemas.microsoft.com/office/word/2010/wordml"
        allowed = {q(n) for n in ("rsidR", "rsidRDefault", "rsidP")}
        id_names = {f"{{{w14}}}paraId", f"{{{w14}}}textId"}
        if any(key not in allowed | id_names for key in paragraph.attrib):
            return False
        identifiers = {
            value.upper() for key, value in paragraph.attrib.items() if key in id_names
        }
        if not identifiers:
            return True
        if not self._paragraph_refs_ready:
            self._paragraph_refs_ready = True
            self._paragraph_refs = set()
            for name, raw in self.original_parts.items():
                if name == "word/document.xml" or not name.endswith(".xml"):
                    continue
                try:
                    root = parse_xml(raw)
                except (ValueError, etree.LxmlError):
                    self._paragraph_refs = None  # Unknown references: preserve IDs.
                    break
                for node in root.iter():
                    for value in [*node.attrib.values(), node.text or ""]:
                        self._paragraph_refs.update(
                            re.findall(
                                r"(?i)(?<![0-9a-f])[0-9a-f]{8}(?![0-9a-f])",
                                value.upper(),
                            )
                        )
        return self._paragraph_refs is not None and not identifiers.intersection(
            self._paragraph_refs
        )

    def remove_empty(self, paragraph, block_id):
        # Only top-level, structurally empty paragraphs with ordinary properties.
        if (
            paragraph.getparent() is None
            or paragraph.getparent().tag != q("body")
            or not self._empty_metadata_safe(paragraph)
        ):
            return False
        if paragraph.xpath(
            ".//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo | .//w:rPrChange",
            namespaces=NS,
        ):
            return False
        allowed_props = {
            q(n) for n in ("pStyle", "jc", "spacing", "ind", "rPr", "widowControl")
        }
        for node in paragraph:
            if node.tag == q("pPr"):
                if any(c.tag not in allowed_props for c in node):
                    return False
            elif node.tag == q("r"):
                if any(c.tag not in {q("rPr"), q("t")} for c in node):
                    return False
                if any((c.text or "") for c in node.findall(q("t"))):
                    return False  # Empty means no characters, not just whitespace.
            else:
                return False
        expected = self.pairs[paragraph]
        expected.getparent().remove(expected)
        paragraph.getparent().remove(paragraph)
        self.events.append(
            {
                "rule": "empty_paragraphs",
                "operation": "authorized_empty_removal",
                "block_id": block_id,
                "count": 1,
            }
        )
        return True

    def replace_toc(self, nodes):
        # Caller must supply the analyzed TOC region explicitly accepted by user.
        for node in nodes:
            expected = self.pairs[node]
            expected.getparent().remove(expected)
            node.getparent().remove(node)
        self.events.append(
            {
                "rule": "toc_replace",
                "operation": "authorized_toc_replacement",
                "count": len(nodes),
            }
        )

    def replace_plain_run(self, run, nodes, rule):
        """Introduce SEQ/REF markup only when every visible character is equal."""
        if (
            run.tag != q("r")
            or run.getparent().tag != q("p")
            or len(run.findall(q("t"))) != 1
            or any(n.tag not in {q("rPr"), q("t")} for n in run)
        ):
            raise DocumentError("Chỉ chuyển trường trên run văn bản đơn giản.")
        original = "".join(run.xpath(".//w:t/text()", namespaces=NS))
        result = "".join(
            t for node in nodes for t in node.xpath(".//w:t/text()", namespaces=NS)
        )
        if original != result:
            raise DocumentError("Chuyển trường đã làm thay đổi chữ hoặc số gốc.")
        parent = run.getparent()
        at = list(parent).index(run)
        expected = self.pairs[run]
        expected.getparent().remove(expected)
        parent.remove(run)
        for index, node in enumerate(nodes):
            self.append_generated(parent, node, rule, at + index)
        self.events.append(
            {"rule": rule, "operation": "text_equal_field_conversion", "count": 1}
        )

    def move_signature(self, nodes, target):
        body = self.package.document.find(q("body"))
        if (
            not nodes
            or any(
                n.tag != q("p") or n.getparent() is not body or n not in self.pairs
                for n in nodes
            )
            or target.getparent() is not body
            or target in nodes
        ):
            raise DocumentError("Khối chữ ký không hợp lệ để bố trí lại.")
        expected_body = self.pairs[body]
        expected_nodes = [self.pairs[n] for n in nodes]
        for node, expected in zip(nodes, expected_nodes):
            body.remove(node)
            expected_body.remove(expected)
        at = list(body).index(target)
        expected_at = list(expected_body).index(self.pairs[target])
        for offset, (node, expected) in enumerate(zip(nodes, expected_nodes)):
            body.insert(at + offset, node)
            expected_body.insert(expected_at + offset, expected)
        self.events.append(
            {
                "rule": "signature",
                "operation": "approved_signature_relocation",
                "count": len(nodes),
            }
        )

    def consume_list_prefix(self, node, prefix, block_id):
        if (
            node.tag != q("t")
            or node not in self.pairs
            or not re.fullmatch(r"\d+[.)]\s+", prefix)
            or not (node.text or "").startswith(prefix)
        ):
            raise DocumentError("Tiền tố danh sách không hợp lệ.")
        node.text = node.text[len(prefix) :]
        self.pairs[node].text = node.text
        self.events.append(
            {
                "rule": "native_list",
                "operation": "numbering_prefix_to_numPr",
                "block_id": block_id,
                "prefix": prefix,
                "count": 1,
            }
        )

    def consume_page_break(self, node):
        """Replace a terminal page break with an approved section boundary."""
        if (
            node.tag != q("br")
            or node.get(q("type")) != "page"
            or node not in self.pairs
        ):
            raise DocumentError("Ngắt trang không hợp lệ để chuyển thành section.")
        expected = self.pairs[node]
        expected.getparent().remove(expected)
        node.getparent().remove(node)
        self.events.append(
            {"rule": "sections", "operation": "page_break_to_section", "count": 1}
        )

    def update_generated_text(self, node, text):
        # Only nodes introduced through append_generated/new_part can be updated.
        if node not in self.generated:
            raise DocumentError("Không tìm thấy nội dung mục lục sinh tự động.")
        self.pairs[node].text = text
        node.text = text

    def verify_bytes(self, data):
        with zipfile.ZipFile(BytesIO(data)) as archive:
            expected_names = set(self.original_parts) | set(self.expected)
            if set(archive.namelist()) != expected_names or len(
                archive.namelist()
            ) != len(expected_names):
                raise DocumentError(
                    "Danh sách thành phần thay đổi ngoài phạm vi đã đăng ký."
                )
            for name in archive.namelist():
                value = archive.read(name)
                if name in self.expected:
                    root = parse_xml(value)
                    actual = (
                        structural_signature(root)
                        if name == "word/document.xml"
                        else canonical(root)
                    )
                    expected = (
                        structural_signature(self.expected[name])
                        if name == "word/document.xml"
                        else canonical(self.expected[name])
                    )
                    if actual != expected:
                        raise DocumentError("Đối chiếu sau đóng gói không thành công.")
                elif value != self.original_parts[name]:
                    raise DocumentError(
                        "Dữ liệu thành phần đính kèm không còn nguyên vẹn."
                    )
        return True

    def verify(self):
        for node, before, block_id in self.locks:
            if node.getparent() is None or canonical(node) != before:
                raise DocumentError(
                    f"Vùng đã khóa bị thay đổi: {block_id}. Không xuất kết quả."
                )
        for name, expected in self.expected.items():
            actual = self.package.roots[name]
            a = (
                structural_signature(actual)
                if name == "word/document.xml"
                else canonical(actual)
            )
            b = (
                structural_signature(expected)
                if name == "word/document.xml"
                else canonical(expected)
            )
            if a != b:
                raise DocumentError(
                    "Đối chiếu toàn vẹn thất bại. Hệ thống đã dừng xuất tài liệu."
                )
        for name, value in self.original_parts.items():
            if name not in self.expected and self.package.parts.get(name) != value:
                raise DocumentError("Một thành phần đính kèm của tài liệu bị thay đổi.")
        for name in set(self.package.roots) - set(self.expected):
            if name not in self.original_parts or canonical(
                self.package.roots[name]
            ) != canonical(parse_xml(self.original_parts[name])):
                raise DocumentError("Có thay đổi XML chưa được đăng ký kiểm chứng.")
        return {
            "verified": True,
            "source_sha256": self.package.source_hash,
            "authorized_edits": self.events,
            "method": "Đối chiếu cấu trúc ngoài thuộc tính trình bày, các phép sửa được chấp thuận và dữ liệu phần đính kèm.",
        }
