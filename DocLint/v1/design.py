"""Explicit role styles, isolated from original styles and protected regions."""

from lxml import etree
from core.profiles import get_profile
from core.xmlutils import W, q, child
from v1.package import canonical


def ensure(parent, name):
    found = parent.find(q(name))
    if found is not None:
        return found
    if (parent.tag, name) in {
        (q("p"), "pPr"),
        (q("r"), "rPr"),
        (q("tbl"), "tblPr"),
        (q("tc"), "tcPr"),
        (q("tr"), "trPr"),
    }:
        found = etree.Element(q(name))
        parent.insert(
            1
            if name == "trPr" and len(parent) and parent[0].tag == q("tblPrEx")
            else 0,
            found,
        )
        return found
    return child(parent, name)


def attrs(parent, name, values):
    node = ensure(parent, name)
    for key, value in values.items():
        node.set(q(key), str(value))
    return node


class Design:
    def __init__(self, profile_id, package, ledger):
        self.profile_id = profile_id
        self.profile = get_profile(profile_id)
        self.font = self.profile["typography"]["default_font"]
        self.size = int(self.profile["typography"]["default_size"])
        self.accent = "183F35" if profile_id == "report" else "000000"
        self.package, self.ledger = package, ledger
        self.ids = {}
        self.definitions = {}
        self.style("body")

    def spec(self, role, level=0):
        p = self.profile["paragraph_rules"]
        values = {
            "size": self.size,
            "font": self.font,
            "color": "202D29" if self.profile_id == "report" else "000000",
            "alignment": p["alignment"],
            "line": p["line_spacing"],
            "before": p["space_before"],
            "after": p["space_after"],
            "first": p["first_line_indent"],
            "bold": False,
            "keep_next": False,
            "keep_lines": False,
            "left": 0,
            "right": 0,
            "hanging": 0,
        }
        if role == "heading":
            values.update(
                size={1: 32, 2: 28, 3: 26}.get(level, 26)
                if self.profile_id == "hust"
                else {1: 36, 2: 30, 3: 26}.get(level, 24),
                color=self.accent,
                bold=True,
                before=360 if level == 1 else 240,
                after=160 if level == 1 else 120,
                line=288,
                first=0,
                alignment="left",
                keep_next=True,
                keep_lines=True,
            )
        elif role == "caption":
            values.update(
                size=24 if self.profile_id == "hust" else 22,
                first=0,
                alignment="center",
                before=100,
                after=160,
                line=276,
                keep_lines=True,
                italic=True,
            )
        elif role == "lead_in":
            values.update(first=0, keep_next=True, keep_lines=True, after=80)
        elif role == "code":
            values.update(
                font="Consolas",
                size=21,
                line=260,
                first=0,
                left=160,
                right=160,
                before=120,
                after=120,
                alignment="left",
                keep_lines=True,
            )
        elif role == "quote":
            values.update(left=720, right=360, first=0, before=120, after=120)
        elif role == "reference":
            values.update(first=0, left=360, hanging=360, before=0, after=80)
        elif role in {"list", "manual_list"}:
            values.update(first=0, before=0, after=80)
            if role == "manual_list":
                values.update(left=360, hanging=360)
        elif role == "table":
            values.update(
                size=self.size if self.profile_id == "hust" else 23,
                first=0,
                alignment="left",
                line=276,
                before=0,
                after=60,
            )
        elif role == "cover":
            values.update(
                first=0,
                alignment="center",
                line=300,
                before=180,
                after=180,
                keep_lines=True,
                keep_next=False,
            )
        elif role == "toc":
            values.update(
                first=0,
                alignment="left",
                left=max(0, level - 1) * 300,
                before=0,
                after=100,
                line=276,
            )
        return values

    def style(self, role, level=0):
        key = (role, level)
        if key in self.ids:
            return self.ids[key]
        spec = self.spec(role, level)
        base_id = f"DL1{self.profile_id}{role}{level or ''}"
        style = etree.Element(
            q("style"), {q("type"): "paragraph", q("styleId"): base_id}, nsmap={"w": W}
        )
        attrs(
            style,
            "name",
            {"val": f"DocLint {self.profile_id} {role} {level or ''}".strip()},
        )
        attrs(style, "next", {"val": f"DL1{self.profile_id}body"})
        attrs(style, "qFormat", {})
        pp = ensure(style, "pPr")
        attrs(pp, "widowControl", {"val": 1})
        attrs(pp, "keepNext", {"val": int(spec["keep_next"])})
        attrs(pp, "keepLines", {"val": int(spec["keep_lines"])})
        attrs(
            pp,
            "spacing",
            {
                "line": spec["line"],
                "lineRule": "auto",
                "before": spec["before"],
                "after": spec["after"],
            },
        )
        ind = {"left": spec["left"], "right": spec["right"]}
        if spec["hanging"]:
            ind["hanging"] = spec["hanging"]
        else:
            ind["firstLine"] = spec["first"]
        attrs(pp, "ind", ind)
        attrs(pp, "jc", {"val": spec["alignment"]})
        attrs(pp, "snapToGrid", {"val": 0})
        if role == "heading":
            attrs(pp, "outlineLvl", {"val": level - 1})
        rp = ensure(style, "rPr")
        attrs(
            rp,
            "rFonts",
            {"ascii": spec["font"], "hAnsi": spec["font"], "cs": spec["font"]},
        )
        attrs(rp, "sz", {"val": spec["size"]})
        attrs(rp, "szCs", {"val": spec["size"]})
        attrs(rp, "color", {"val": spec["color"]})
        if spec["bold"]:
            attrs(rp, "b", {"val": 1})
        if spec.get("italic"):
            attrs(rp, "i", {"val": 1})
        # Never mutate an existing style, which may also be used in a locked region.
        for suffix in range(100):
            sid = base_id if suffix == 0 else f"{base_id}x{suffix}"
            style.set(q("styleId"), sid)
            old = self.package.styles.find(f"{q('style')}[@{q('styleId')}='{sid}']")
            if old is None:
                self.ledger.append_generated(
                    self.package.styles, style, "template_style"
                )
                self.ids[key] = sid
                return sid
            if canonical(old) == canonical(style):
                self.ids[key] = sid
                return sid
        from core.processor import DocumentError

        raise DocumentError("Có quá nhiều style trùng tên; hãy làm sạch tệp trước.")
