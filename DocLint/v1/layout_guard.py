"""Protect positioned text together with its page anchors and shared geometry.

Only explicit page/section boundaries delimit a safe unit. Rendered page-break
markers are caches, not boundaries. A frame in an unpartitioned section therefore
protects the surrounding unit too; ordinary text is edited only outside it.
"""

from core.xmlutils import NS, q
from v1.analysis import on

WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
VML = "urn:schemas-microsoft-com:vml"


def ends_main_story_page(analysis, block):
    node = analysis.elements[block["id"]]
    if node.tag != q("p"):
        return False
    if node.xpath('./w:r/w:br[@w:type="page"]', namespaces=NS):
        return True
    if node.find("w:pPr/w:sectPr", NS) is None:
        return False
    index = block.get("section")
    if index is None or index + 1 >= len(analysis.section_nodes):
        return False
    # The following section's start type controls the boundary. Continuous
    # and next-column starts do not prove that the preceding page has ended.
    kind = analysis.section_nodes[index + 1][1].find(q("type"))
    return kind is None or kind.get(q("val"), "nextPage") not in {
        "continuous",
        "nextColumn",
    }


def _paragraph_attached(box):
    """A label attached to an inline/paragraph graphic moves with its anchor."""
    for parent in box.iterancestors():
        if parent.tag == f"{{{WP}}}inline":
            return True
        if parent.tag == f"{{{WP}}}anchor":
            vertical = parent.find(f"{{{WP}}}positionV")
            return vertical is not None and vertical.get("relativeFrom") in {
                "paragraph",
                "line",
            }
        if parent.tag == f"{{{VML}}}shape":
            style = (parent.get("style") or "").replace(" ", "").lower()
            return (
                "mso-position-vertical-relative:text" in style
                or "mso-position-vertical-relative:line" in style
            )
    return False


def layout_policy(analysis):
    positioned = set()
    isolated = set()
    frames = textboxes = floating_tables = 0
    for block in analysis.blocks:
        node = analysis.elements[block["id"]]
        paragraphs = [node] if node.tag == q("p") else node.findall(".//" + q("p"))
        for paragraph in paragraphs:
            frame = analysis.resolver.property(paragraph, "w:pPr/w:framePr")
            if frame is not None and frame.get(q("dropCap"), "none") == "none":
                frames += 1
                positioned.add(block["id"])
        boxes = node.findall(".//" + q("txbxContent"))
        tables = node.findall(".//" + q("tblpPr"))
        textboxes += len(boxes)
        floating_tables += len(tables)
        if boxes and all(_paragraph_attached(box) for box in boxes):
            isolated.add(block["id"])
        elif boxes:
            positioned.add(block["id"])
        if tables:
            positioned.add(block["id"])

    units, current = [], []
    for block in analysis.blocks:
        node = analysis.elements[block["id"]]
        if (
            node.tag == q("p")
            and block["id"] not in positioned
            and on(analysis.resolver.property(node, "w:pPr/w:pageBreakBefore"))
        ):
            if current:
                units.append(current)
                current = []
        current.append(block)
        if ends_main_story_page(analysis, block):
            units.append(current)
            current = []
    if current:
        units.append(current)

    protected = set()
    regions = []
    for unit in units:
        if any(b["id"] in positioned for b in unit):
            protected.update(b["id"] for b in unit)
            regions.append({"start": unit[0]["id"], "end": unit[-1]["id"]})
    sections = sorted(
        {
            b["section"]
            for b in analysis.blocks
            if b["id"] in protected and b.get("section") is not None
        }
    )
    editable = [
        b["id"]
        for b in analysis.blocks
        if b["id"] not in protected
        and b["role"] not in {"empty", "protected", "code", "toc"}
        and not b.get("complex_section")
    ]
    for block in analysis.blocks:
        block["layout_locked"] = block["id"] in protected or block["id"] in isolated
    return {
        "kind": "fixed"
        if protected and not editable
        else "mixed"
        if protected
        else "flow",
        "protected_block_ids": [
            b["id"] for b in analysis.blocks if b["id"] in protected
        ],
        "protected_regions": regions,
        "isolated_object_ids": sorted(isolated - protected),
        "protected_sections": sections,
        "editable_block_ids": editable,
        "preserve_only": bool(protected) and not editable,
        "frames": frames,
        "textboxes": textboxes,
        "floating_tables": floating_tables,
    }
