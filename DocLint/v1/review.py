"""Group comparable ambiguities; leave established roles out of the questionnaire."""

from collections import defaultdict
import re
from v1.analysis import folded, text_of
from v1.hierarchy import ROOT


def review_plan(analysis):
    blocks = analysis.blocks
    cover_position = next(
        (b["position"] for b in blocks if b["id"] == analysis.cover_end), -1
    )
    eligible = [
        b
        for b in blocks
        if b["position"] > cover_position
        and not b.get("protected")
        and not b.get("layout_locked")
        and not b.get("region")
        and b["role"] != "toc"
    ]
    families = defaultdict(list)
    for block in eligible:
        if block["role"] != "heading" or block["certainty"] == "certain":
            continue
        if block.get("heading_scope"):
            # Scoped sequences already went through parent/child validation.
            # Do not promote them a second time without a supported parent.
            continue
        text = folded(block["text"])
        kind = (
            "chapter"
            if ROOT.match(text)
            else "decimal"
            if re.match(r"^\d+(?:\.\d+)+\.?\s", text)
            else "single"
        )
        families[(kind, block["level"], block.get("heading_scope"))].append(block)
    automatic = {b["id"]: b["level"] for b in eligible if b.get("hierarchy_auto")}
    for (kind, _, _scope), members in families.items():
        separated = all(
            any(
                b["role"] == "body" and b["text"]
                for b in blocks
                if left["position"] < b["position"] < right["position"]
            )
            for left, right in zip(members, members[1:])
        )
        labels = []
        for b in members:
            match = re.match(
                r"^(?:(?:chuong|chapter|phan|part|bai tap|exercise|bai|section)\s+)?(\d+(?:\.\d+)*)",
                folded(b["text"]),
            )
            labels.append(
                tuple(int(v) for v in match.group(1).split(".")) if match else ()
            )
        if (
            kind in {"chapter", "decimal"}
            and len(members) >= 2
            and len(set(labels)) == len(members)
            and all(labels)
            and labels == sorted(labels)
            and separated
            and all(b["bold"] or b["text"].isupper() for b in members)
        ):
            automatic.update({b["id"]: b["level"] for b in members})
    grouped = defaultdict(list)
    for b in eligible:
        if (
            b["role"] in {"heading", "emphasis"}
            and b["certainty"] != "certain"
            and b["id"] not in automatic
        ):
            text = folded(b["text"])
            kind = (
                "chapter"
                if ROOT.match(text)
                else "decimal"
                if re.match(r"^\d+(?:\.\d+)+\.?\s", text)
                else "numbered"
                if re.match(r"^\d+[.)]\s", text)
                else "emphasis"
            )
            grouped[(kind, b.get("level") or 1)].append(b)
    heading_groups = []
    labels = {
        "chapter": "Các dòng có nhãn chương/phần/bài",
        "decimal": "Các dòng đánh số nhiều cấp",
        "numbered": "Các dòng đánh số đơn",
        "emphasis": "Các dòng ngắn được nhấn mạnh",
    }
    for (kind, level), members in grouped.items():
        heading_groups.append(
            {
                "id": f"heading-{kind}-{level}",
                "kind": kind,
                "level": level,
                "label": labels[kind],
                "block_ids": [b["id"] for b in members],
                "default": "keep",
            }
        )
    manual = defaultdict(list)
    for b in eligible:
        if b["role"] != "body":
            continue
        text = text_of(analysis.elements[b["id"]])
        leading = len(text) - len(text.lstrip(" "))
        if b["has_tab"] or leading >= 6 and len(b["text"]) < 100:
            manual["tabs" if b["has_tab"] else "spaces"].append(b["id"])
    layout_groups = [
        {
            "id": f"layout-{kind}",
            "label": "Đoạn căn bằng Tab chưa rõ ý đồ"
            if kind == "tabs"
            else "Đoạn ngắn căn bằng nhiều Space",
            "block_ids": ids,
            "default": "keep",
        }
        for kind, ids in manual.items()
    ]
    uncertain_tables = [
        b["id"]
        for b in eligible
        if b["type"] == "table"
        and b.get("format_safe", b["simple"])
        and not b["header"]
        and b["suggest_header"]
    ]
    caption_groups = defaultdict(list)
    for b in eligible:
        if b["role"] == "caption" and len(b.get("targets", [])) > 1:
            targets = {
                target["id"]: target
                for target in blocks
                if target["id"] in b["targets"]
            }
            before = [
                bid
                for bid, target in targets.items()
                if target["position"] < b["position"]
            ]
            after = [
                bid
                for bid, target in targets.items()
                if target["position"] > b["position"]
            ]
            if len(before) == len(after) == 1:
                key = (targets[before[0]]["role"], targets[after[0]]["role"])
                caption_groups[key].append(
                    {"id": b["id"], "previous": before[0], "next": after[0]}
                )
    captions = [
        {
            "id": f"caption-{before}-{after}",
            "label": "Chú thích nằm giữa hai đối tượng phù hợp",
            "members": members,
            "block_ids": [m["id"] for m in members],
            "default": "keep",
        }
        for (before, after), members in caption_groups.items()
    ]
    cover_candidates = []
    if analysis.cover_end:
        cover_candidates.append(analysis.cover_end)
        # Offer only a nearby alternative boundary, rather than every paragraph.
        following = next(
            (
                b
                for b in blocks
                if b["position"] > cover_position and b["role"] == "heading"
            ),
            None,
        )
        if following:
            previous = [
                b
                for b in blocks
                if cover_position < b["position"] < following["position"] and b["text"]
            ]
            if (
                previous
                and previous[-1]["position"] <= 50
                and re.search(
                    r"sinh vien|giang vien|ma (?:so|lop)|nhom|ho ten|thang|nam\s+20",
                    folded(previous[-1]["text"]),
                )
            ):
                cover_candidates.append(previous[-1]["id"])
    counts = {
        "existing_headings": sum(
            b["role"] == "heading" and b["certainty"] == "certain" for b in eligible
        ),
        "automatic_headings": len(automatic),
        "body": sum(b["role"] == "body" for b in eligible),
        "tables": sum(b["type"] == "table" for b in eligible),
        "images": sum(b["role"] == "image" for b in eligible),
        "linked_captions": sum(
            b["role"] == "caption" and bool(b.get("target")) for b in eligible
        ),
    }
    return {
        "automatic_headings": automatic,
        "heading_groups": heading_groups,
        "layout_groups": layout_groups,
        "table_groups": [
            {
                "id": "table-header",
                "label": "Hàng đầu có vẻ là tên cột",
                "block_ids": uncertain_tables,
                "default": "keep",
            }
        ]
        if uncertain_tables
        else [],
        "caption_groups": captions,
        "cover_candidates": cover_candidates,
        "cover_explicit": analysis.cover_explicit,
        "counts": counts,
        "question_count": len(heading_groups)
        + len(layout_groups)
        + bool(uncertain_tables)
        + len(captions),
    }
