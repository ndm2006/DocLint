"""Cover semantics and explicit boundaries shared by analysis and formatting."""

import re
from core.xmlutils import q
from v1.analysis import CHAPTER, folded, on
from v1.layout_guard import ends_main_story_page

TITLE = re.compile(
    r"^(?:bao cao|tieu luan|do an|luan van|(?:final |research |technical )?"
    r"(?:essay|report|thesis|dissertation))\b",
    re.I,
)
LABEL = re.compile(
    r"^(?:dai hoc|truong|bo giao duc|khoa|de tai|mon hoc|ma (?:so|lop|mon)|"
    r"giang vien|sinh vien|nhom|danh sach|ho ten|nguoi (?:huong dan|thuc hien)|"
    r"university|college|school|institute|subject|course|instructor|supervisor|"
    r"student|group|members|topic|title|hanoi|ha noi|ho chi minh|ngay|date)\b|"
    r"\buniversity of\b",
    re.I,
)
BODY_START = re.compile(
    r"^(?:loi (?:mo dau|cam on)|mo dau|tom tat|tong quan|gioi thieu|muc luc|"
    r"abstract|introduction|acknowledg(?:e)?ments|contents|table of contents)\s*[:.]?\s*$",
    re.I,
)


def cover_label(text):
    text = folded(text)
    return bool(TITLE.match(text) or LABEL.search(text))


def explicit_cover_end(analysis, first):
    """Prefer the first explicit cover boundary over cosmetic Heading styles.

    A chapter, named body section or ordinary prose before that boundary stops
    the proposal, so a page break in the body cannot swallow the introduction.
    """
    previous = None
    for block in first:
        node = analysis.elements[block["id"]]
        text = folded(block["text"])
        if (
            node.tag == q("p")
            and previous
            and on(analysis.resolver.property(node, "w:pPr/w:pageBreakBefore"))
        ):
            return previous["id"]
        if (
            CHAPTER.match(text)
            or BODY_START.match(text)
            or (block["role"] == "heading" and re.match(r"^\d+[.)\s]", text))
        ):
            return None
        if (
            block["role"] == "body"
            and len(text.split()) > 8
            and not cover_label(text)
            and block.get("alignment") != "center"
        ):
            return None
        if ends_main_story_page(analysis, block):
            return block["id"]
        previous = block
    return None
