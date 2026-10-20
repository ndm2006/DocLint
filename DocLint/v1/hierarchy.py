"""Infer manual heading levels from scoped sequences, not isolated prefixes.

Existing Word headings remain authoritative. Repeated child numbers are valid
inside different chapters/exercises; compact lists never become headings merely
because their labels form a sequence.
"""

from collections import defaultdict
import re
from v1.analysis import DECIMAL, SINGLE, folded

ROOT = re.compile(
    r"^(chuong|chapter|phan|part|bai tap|exercise|bai|section)\s+"
    r"(\d+|[ivxlcdm]+)(?=[.:)\s]|$)",
    re.I,
)
ROMAN = re.compile(r"^([IVXLCDM]+)[.)]\s+\S")
ALPHA = re.compile(r"^([A-Za-z])[.)]\s+\S")
CONTENT = {"body", "list", "manual_list", "quote", "image", "table", "lead_in"}


def _number(label):
    if label.isdigit():
        return int(label)
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    digits = [values[c] for c in label.lower()]
    return sum(
        -v if i + 1 < len(digits) and v < digits[i + 1] else v
        for i, v in enumerate(digits)
    )


def _visual(block):
    return block.get("bold") or block["text"].isupper()


def _suggest(block, level, reason):
    if block["certainty"] == "certain" and block["role"] == "heading":
        return
    block.update(
        role="heading", level=min(6, level), certainty="suggested", reason=reason
    )


def _coherent(members, labels, blocks):
    return (
        len(members) >= 2
        and len(set(labels)) == len(labels)
        and labels == sorted(labels)
        and all(_visual(b) for b in members)
        and all(
            any(
                b["role"] in CONTENT and b["text"]
                for b in blocks
                if left["position"] < b["position"] < right["position"]
            )
            for left, right in zip(members, members[1:])
        )
    )


def _automatic(members, labels, blocks, parent=None):
    approved = (
        parent is None
        or parent.get("hierarchy_auto")
        or (parent["role"] == "heading" and parent["certainty"] == "certain")
    )
    if approved and _coherent(members, labels, blocks):
        for block in members:
            if block["certainty"] != "certain":
                block["hierarchy_auto"] = True


def refine_hierarchy(analysis):
    cover = next(
        (b["position"] for b in analysis.blocks if b["id"] == analysis.cover_end), -1
    )
    toc = set(analysis.toc_nodes)
    blocks = [
        b
        for b in analysis.blocks
        if b["position"] > cover
        and analysis.elements[b["id"]] not in toc
        and not b.get("protected")
        and not b.get("region")
    ]
    roots = []
    families = defaultdict(list)
    outer_part = None
    for block in blocks:
        if block["role"] != "heading":
            continue
        match = ROOT.match(folded(block["text"]))
        if match:
            family, number = match.groups()
            if family in {"phan", "part"}:
                outer_part = block
            elif family in {"chuong", "chapter"} and outer_part:
                _suggest(
                    block,
                    outer_part["level"] + 1,
                    "Chương nằm trong phần lớn đã nhận diện.",
                )
            else:
                outer_part = None
            roots.append(block)
            families[
                (
                    family,
                    outer_part["id"]
                    if outer_part is not block and outer_part
                    else None,
                )
            ].append((block, _number(number)))
        elif block["certainty"] == "certain" and block.get("level") == 1:
            roots.append(block)
            outer_part = None
    for rows in families.values():
        _automatic([b for b, _ in rows], [n for _, n in rows], blocks)

    # Roman major sections can be top-level, or children of a named chapter.
    roman_groups = defaultdict(list)
    for block in blocks:
        match = ROMAN.match(block["text"])
        if not match or not _visual(block) or len(block["text"]) >= 160:
            continue
        if block["role"] not in {
            "body",
            "emphasis",
            "lead_in",
            "manual_list",
            "heading",
        }:
            continue
        parent = next(
            (r for r in reversed(roots) if r["position"] < block["position"]), None
        )
        roman_groups[parent["id"] if parent else None].append(
            (block, _number(match[1]), parent)
        )
    for rows in roman_groups.values():
        members, labels = [r[0] for r in rows], [r[1] for r in rows]
        if labels != list(range(labels[0], labels[0] + len(labels))) or not _coherent(
            members, labels, blocks
        ):
            continue
        parent = rows[0][2]
        for block in members:
            _suggest(
                block,
                parent["level"] + 1 if parent else 1,
                "Chuỗi mục số La Mã có nội dung riêng giữa các mục.",
            )
        _automatic(members, labels, blocks, parent)
        roots.extend(members)
    roots.sort(key=lambda b: b["position"])

    # Each root gets its own numbering namespace, so 1., 2. may restart.
    for index, parent in enumerate(roots):
        end = roots[index + 1]["position"] if index + 1 < len(roots) else float("inf")
        children = [b for b in blocks if parent["position"] < b["position"] < end]
        singles = [
            b for b in children if b["role"] == "heading" and SINGLE.match(b["text"])
        ]
        for block in singles:
            _suggest(
                block,
                parent["level"] + 1,
                "Mục đánh số đơn nằm dưới chương/phần/bài hiện tại.",
            )
            block["heading_scope"] = parent["id"]
        _automatic(
            singles, [int(SINGLE.match(b["text"])[1]) for b in singles], blocks, parent
        )
        decimals = defaultdict(list)
        for block in children:
            match = DECIMAL.match(block["text"])
            if block["role"] != "heading" or not match:
                continue
            depth = match[1].count(".") + 1
            level = depth + parent["level"] - (0 if singles else 1)
            _suggest(
                block, level, "Cấp đề mục nhiều cấp được đối chiếu trong phần hiện tại."
            )
            block["heading_scope"] = parent["id"]
            decimals[block["level"]].append(block)
        for members in decimals.values():
            _automatic(
                members,
                [
                    tuple(map(int, DECIMAL.match(b["text"])[1].split(".")))
                    for b in members
                ],
                blocks,
                parent,
            )

    # Lettered subsections need both a parent and expanded, ordered siblings.
    groups = defaultdict(list)
    parent = None
    root_ids = {b["id"] for b in roots}
    for block in blocks:
        match = ALPHA.match(block["text"])
        if block["role"] == "heading" and (not match or block["id"] in root_ids):
            parent = block
        elif (
            match
            and parent
            and _visual(block)
            and len(block["text"]) < 160
            and block["id"] not in root_ids
        ):
            groups[(parent["id"], match[1].isupper())].append(
                (block, ord(match[1].lower()), parent)
            )
    for rows in groups.values():
        members, labels = [r[0] for r in rows], [r[1] for r in rows]
        if labels != list(range(labels[0], labels[0] + len(labels))) or not _coherent(
            members, labels, blocks
        ):
            continue
        parent = rows[0][2]
        for block in members:
            _suggest(
                block,
                parent["level"] + 1,
                "Các tiểu mục chữ cái có phần nội dung riêng dưới cùng đề mục cha.",
            )
            block["heading_scope"] = parent["id"]
        _automatic(members, labels, blocks, parent)
