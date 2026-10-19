"""Formatting-only fixes: never remove a paragraph, a character, or a tab."""
from collections import Counter
import re
from lxml import etree
from core.xmlutils import NS, q, child

HEADING = re.compile(r'^(?:(?:Chương|Chapter|Phần|Part|Bài|Section)\s*(?:\d+|[IVXLCDM]+)\b|[IVXLCDM]+\.|\d+(?:\.\d+)*[.\s])', re.I)
SPECIAL_STYLE = re.compile(r'heading|title|subtitle|toc|caption|tiêu đề|mục lục|chú thích', re.I)
SYMBOL_FONTS = {'symbol', 'wingdings', 'wingdings 2', 'wingdings 3', 'webdings', 'mt extra', 'cambria math'}

class DocFixer:
    def __init__(self, profile, styles_tree=None):
        self.profile = profile
        self.namespaces = NS
        self.styles = {}
        if styles_tree is not None:
            self.styles = {s.get(q('styleId')): s for s in styles_tree.findall(q('style'))}
        self.changes = Counter()
        self.checks = Counter()
        self.warnings = Counter()

    def _property(self, parent, name, attrs, category, remove=()):
        node = parent.find(q(name))
        before = etree.tostring(node) if node is not None else None
        node = child(parent, name)
        for attr in remove:
            node.attrib.pop(q(attr), None)
        for attr, value in attrs.items():
            node.set(q(attr), str(value))
        self.checks[category] += 1
        if before != etree.tostring(node):
            self.changes[category] += 1
        return node

    def _style_chain(self, paragraph):
        style_id = paragraph.find('w:pPr/w:pStyle', NS)
        style_id = style_id.get(q('val')) if style_id is not None else 'Normal'
        seen = set()
        while style_id and style_id not in seen:
            seen.add(style_id)
            style = self.styles.get(style_id)
            yield style_id, style
            based = style.find(q('basedOn')) if style is not None else None
            style_id = based.get(q('val')) if based is not None else None

    def body_paragraphs(self, tree):
        for p in tree.findall('w:body/w:p', NS):
            text = ''.join(p.xpath('.//w:t/text()', namespaces=NS))
            if not text.strip():
                continue
            # Keep lists, fields, formulas, tracked revisions and drawing layouts.
            if p.xpath('.//w:drawing | .//w:pict | .//w:object | .//m:oMath | .//m:oMathPara | .//w:fldChar | .//w:instrText | .//w:fldSimple | .//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo | ./w:pPr/w:numPr | ./w:pPr/w:sectPr', namespaces=NS):
                continue
            chain = list(self._style_chain(p))
            if any(SPECIAL_STYLE.search(sid or '') or (s is not None and (
                SPECIAL_STYLE.search(' '.join(s.xpath('./w:name/@w:val', namespaces=NS))) or
                s.find('w:pPr/w:outlineLvl', NS) is not None or s.find('w:pPr/w:numPr', NS) is not None)) for sid, s in chain):
                continue
            if p.find('w:pPr/w:outlineLvl', NS) is not None:
                continue
            props = [p.find(q('pPr'))] + [s.find(q('pPr')) for _, s in chain if s is not None]
            alignment = next((n.find(q('jc')).get(q('val')) for n in props if n is not None and n.find(q('jc')) is not None), None)
            if alignment in {'center', 'right', 'end'}:
                continue
            if HEADING.match(text.strip()):
                self.warnings['headings'] += 1
                continue
            if p.xpath('.//w:tab', namespaces=NS) or text != text.lstrip():
                self.warnings['manual_spacing'] += 1
                continue
            runs = p.xpath('./w:r[w:t]', namespaces=NS)
            # Short bold blocks are often covers, captions or signatures.
            if len(text.strip()) < 100 and runs and all(r.find('w:rPr/w:b', NS) is not None for r in runs):
                continue
            yield p

    def fix_margins(self, tree):
        for section in tree.xpath('.//w:sectPr', namespaces=NS):
            size = section.find(q('pgSz'))
            columns = section.find(q('cols'))
            landscape = size is not None and (size.get(q('orient')) == 'landscape' or int(size.get(q('w'), '0')) > int(size.get(q('h'), '99999')))
            if landscape or (columns is not None and (int(columns.get(q('num'), '1')) > 1 or len(columns))):
                self.warnings['complex_sections'] += 1
                continue
            self._property(section, 'pgMar', self.profile['margin_rules'], 'margins')
            self._property(section, 'pgSz', self.profile['page_rules'], 'page_size')
        return tree

    def fix_fonts(self, tree):
        font = self.profile['typography']['default_font']
        size = self.profile['typography']['default_size']
        for p in self.body_paragraphs(tree):
            for run in p.xpath('.//w:r[w:t]', namespaces=NS):
                existing = run.find('w:rPr/w:rFonts', NS)
                if existing is not None and any(v.lower() in SYMBOL_FONTS for v in existing.attrib.values()):
                    self.warnings['symbol_fonts'] += 1
                    continue
                # A character style may encode symbols or special typography.
                if run.find('w:rPr/w:rStyle', NS) is not None:
                    continue
                props = run.find(q('rPr'))
                if props is None:
                    props = etree.Element(q('rPr'))
                    run.insert(0, props)
                self._property(props, 'rFonts', {'ascii': font, 'hAnsi': font, 'cs': font}, 'fonts', ('asciiTheme', 'hAnsiTheme', 'cstheme'))
                if props.find(q('vertAlign')) is None:
                    self._property(props, 'sz', {'val': size}, 'font_size')
                    self._property(props, 'szCs', {'val': size}, 'font_size')
        return tree

    def fix_global_styles(self, styles_tree):
        defaults = child(child(child(styles_tree, 'docDefaults'), 'rPrDefault'), 'rPr')
        font = self.profile['typography']['default_font']
        self._property(defaults, 'rFonts', {'ascii': font, 'hAnsi': font, 'cs': font}, 'default_font', ('asciiTheme', 'hAnsiTheme', 'cstheme'))
        # Do not flatten heading sizes, symbol styles, footnotes, or equations.
        return styles_tree

    def fix_fake_headings(self, tree):
        """Compatibility entry point: ambiguous headings are now warnings only."""
        return tree

    def fix_paragraphs(self, tree):
        rules = self.profile['paragraph_rules']
        for p in self.body_paragraphs(tree):
            props = p.find(q('pPr'))
            if props is None:
                props = etree.Element(q('pPr'))
                p.insert(0, props)
            self._property(props, 'jc', {'val': rules['alignment']}, 'paragraphs')
            self._property(props, 'spacing', {'line': rules['line_spacing'], 'lineRule': 'auto', 'before': rules['space_before'], 'after': rules['space_after']}, 'paragraphs', ('beforeAutospacing', 'afterAutospacing', 'beforeLines', 'afterLines'))
            # Existing horizontal indents may encode a quotation or signature.
            if props.find(q('ind')) is None:
                self._property(props, 'ind', {'firstLine': rules['first_line_indent']}, 'paragraphs')
            self._property(props, 'widowControl', {'val': '1'}, 'paragraphs')
        for p in tree.findall('w:body/w:p', NS):
            if p.xpath('.//w:drawing/wp:inline', namespaces={**NS, 'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}) and not p.xpath('.//w:t | .//w:pict | .//m:oMath | .//w:fldChar | .//w:instrText | .//w:ins | .//w:del', namespaces=NS) and not p.xpath('.//wp:anchor', namespaces={'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}):
                props = p.find(q('pPr'))
                if props is None:
                    props = etree.Element(q('pPr'))
                    p.insert(0, props)
                self._property(props, 'jc', {'val': 'center'}, 'images')
        return tree
