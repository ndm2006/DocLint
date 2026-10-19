"""Small, deliberately restricted OpenXML helpers."""
from copy import deepcopy
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W, 'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}

def q(name):
    return f'{{{W}}}{name}'

# ECMA-376 child ordering matters to Word, even when an XML parser accepts it.
ORDERS = {
    'pPr': 'pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange'.split(),
    'rPr': 'rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath rPrChange'.split(),
    'sectPr': 'headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange'.split(),
    'tblPr': 'tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription tblPrChange'.split(),
    'tcPr': 'cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign hideMark cellIns cellDel cellMerge tcPrChange'.split(),
    'trPr': 'cnfStyle divId gridBefore gridAfter wBefore wAfter cantSplit trHeight tblHeader tblCellSpacing jc hidden ins del trPrChange'.split(),
    'docDefaults': ['rPrDefault', 'pPrDefault'],
    'styles': ['docDefaults', 'latentStyles', 'style'],
}

def child(parent, name):
    found = parent.find(q(name))
    if found is not None:
        return found
    found = etree.Element(q(name))
    order = ORDERS.get(etree.QName(parent).localname, [])
    rank = order.index(name) if name in order else len(order)
    for i, other in enumerate(parent):
        local = etree.QName(other).localname if isinstance(other.tag, str) else ''
        if local in order and order.index(local) > rank:
            parent.insert(i, found)
            break
    else:
        parent.append(found)
    return found


def parse_xml(data):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False,
                             huge_tree=False, remove_blank_text=False)
    root = etree.fromstring(data, parser)
    if root.getroottree().docinfo.doctype:
        raise ValueError('Tài liệu có khai báo DTD không được hỗ trợ.')
    return root


def content_signature(root):
    """Compare everything except the exact formatting properties we allow to edit.

    Text, whitespace inside text nodes, fields, math, drawings, revisions, lists,
    tables, links, and relationships remain part of this structural signature.
    XML indentation and unused namespace prefixes are not document content.
    """
    root = deepcopy(root)
    allowed = {
        q('pPr'): {q(n) for n in ('jc', 'spacing', 'ind', 'widowControl')},
        q('rPr'): {q(n) for n in ('rFonts', 'sz', 'szCs')},
        q('sectPr'): {q('pgMar'), q('pgSz')},
    }
    containers = {q(n) for n in ('pPr', 'rPr', 'rPrDefault', 'docDefaults')}
    for node in list(root.iter())[::-1]:
        parent = node.getparent()
        if parent is None:
            continue
        if node.tag in allowed.get(parent.tag, set()):
            # Formatting properties are leaf elements; never hide embedded content.
            if len(node) or (node.text or '').strip():
                raise ValueError('Thuộc tính định dạng chứa cấu trúc không được hỗ trợ.')
            parent.remove(node)
        elif node.tag in containers and not len(node) and not node.attrib and not (node.text or '').strip():
            parent.remove(node)

    def signature(node):
        if not isinstance(node.tag, str):
            return ('comment', node.text)
        text = node.text
        if len(node) and text and not text.strip():
            text = None  # XML indentation, not w:t character data.
        tail = node.tail if node.tail and node.tail.strip() else None
        return (node.tag, tuple(sorted(node.attrib.items())), text, tail,
                tuple(signature(c) for c in node))
    return signature(root)
