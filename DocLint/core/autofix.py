from lxml import etree
import re

class DocFixer:
    def __init__(self, profile):
        self.profile = profile
        self.namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

    def fix_margins(self, tree):
        expected_left = self.profile["margin_rules"]["left"]
        expected_right = self.profile["margin_rules"]["right"]
        pg_mar_tags = tree.xpath('.//w:sectPr/w:pgMar', namespaces=self.namespaces)
        for pg_mar in pg_mar_tags:
            pg_mar.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}left', expected_left)
            pg_mar.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}right', expected_right)
        return tree

    def fix_fonts(self, tree):
        # 1. Cắt bỏ hoàn toàn nhiễu cục bộ (Các thẻ rFonts rác nằm rải rác)
        font_tags = tree.xpath('.//w:rPr/w:rFonts', namespaces=self.namespaces)
        for tag in font_tags:
            parent = tag.getparent()
            if parent is not None:
                parent.remove(tag)
        return tree

    def fix_global_styles(self, styles_tree):
        # 2. TẤN CÔNG TRỤ SỞ CHÍNH: Can thiệp vào file styles.xml
        expected_font = self.profile["typography"]["default_font"]
        
        # Tìm mọi cấu hình font gốc trong file styles.xml
        all_rFonts = styles_tree.xpath('.//w:rFonts', namespaces=self.namespaces)
        
        for rFonts in all_rFonts:
            # Bẻ gãy liên kết với Theme Calibri của Microsoft
            for attr in list(rFonts.keys()):
                if 'Theme' in attr:
                    del rFonts.attrib[attr]
            
            # Ép cứng font chuẩn vào lõi hệ thống
            rFonts.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii', expected_font)
            rFonts.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hAnsi', expected_font)
            rFonts.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}cs', expected_font)
            
        return styles_tree
    def fix_fake_headings(self, tree):
        heading_pattern = re.compile(
            r'^((Chương|Chapter|Phần|Part|Bài|Section)\s*(?:\d+|[IVX]+)|[IVX]+\.|[0-9]+(\.[0-9]+)*\.*)', 
            re.IGNORECASE
        )
        paragraphs = tree.xpath('.//w:p', namespaces=self.namespaces)
        
        for p in paragraphs:
            bolds = p.xpath('.//w:rPr/w:b', namespaces=self.namespaces)
            if bolds:
                texts = p.xpath('.//w:t/text()', namespaces=self.namespaces)
                full_text = "".join(texts).strip()
                
                # Suy đoán 1: Cấu trúc giống tiêu đề và ngắn (< 100 ký tự)
                if full_text and len(full_text) < 100 and heading_pattern.match(full_text):
                    
                    # Suy đoán 2: Không phải là một câu văn kể lể kết thúc bằng dấu câu
                    if not full_text.endswith(('.', '?', '!')):
                        
                        # CHÚ Ý: Toàn bộ khối này đã được thụt lề vào trong
                        pStyle_val = p.xpath('.//w:pPr/w:pStyle/@w:val', namespaces=self.namespaces)
                        if not pStyle_val or 'Heading' not in pStyle_val[0]:
                            
                            # 1. Tìm hoặc tạo thẻ thuộc tính đoạn văn <w:pPr>
                            pPr = p.find('w:pPr', namespaces=self.namespaces)
                            if pPr is None:
                                pPr = etree.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
                                p.insert(0, pPr)
                            
                            # 2. Xóa Style cũ (nếu có)
                            old_style = pPr.find('w:pStyle', namespaces=self.namespaces)
                            if old_style is not None:
                                pPr.remove(old_style)
                                
                            # 3. ÉP KHUÔN HEADING 1
                            new_style = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pStyle')
                            new_style.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'Heading1')
        return tree
    def fix_paragraphs(self, tree):
        p_rules = self.profile.get("paragraph_rules", {})
        default_align = p_rules.get("alignment", "both")
        default_indent = p_rules.get("first_line_indent", "720")
        line_val = p_rules.get("line_spacing", "360")
        space_val = p_rules.get("space_before", "120")
        
        paragraphs = tree.xpath('.//w:p', namespaces=self.namespaces)
        
        for p in paragraphs:
            # 1. Bỏ qua Heading
            pStyle = p.xpath('.//w:pPr/w:pStyle/@w:val', namespaces=self.namespaces)
            if pStyle and 'Heading' in pStyle[0]:
                continue
                
            # 2. ANTI-SPAM: Xóa các đoạn rỗng (Enter thừa)
            texts = p.xpath('.//w:t/text()', namespaces=self.namespaces)
            full_text_clean = "".join(texts).strip()
            drawings = p.xpath('.//w:drawing', namespaces=self.namespaces)
            br = p.xpath('.//w:br', namespaces=self.namespaces)
            
            if not full_text_clean and not drawings and not br:
                parent = p.getparent()
                if parent is not None:
                    parent.remove(p)
                continue

            # 3. QUÉT RÁC & ĐẾM SỐ LƯỢNG (Sweeper & Counter)
            leading_spaces_count = 0
            text_started = False
            
            runs = p.xpath('.//w:r', namespaces=self.namespaces)
            for r in runs:
                if text_started:
                    break
                    
                # Xóa và đếm thẻ Tab
                tabs = r.xpath('.//w:tab', namespaces=self.namespaces)
                if tabs:
                    leading_spaces_count += len(tabs) * 5  # Quy đổi 1 tab tương đương 5 dấu cách
                    for tab in tabs:
                        tab.getparent().remove(tab)
                        
                # Xóa và đếm khoảng trắng ở đầu thẻ Text
                t_nodes = r.xpath('.//w:t', namespaces=self.namespaces)
                for t in t_nodes:
                    if t.text:
                        original_len = len(t.text)
                        stripped_text = t.text.lstrip()
                        removed_spaces = original_len - len(stripped_text)
                        
                        leading_spaces_count += removed_spaces
                        t.text = stripped_text
                        
                        if len(stripped_text) > 0:
                            text_started = True
                            break

           # 4. SUY ĐOÁN Ý ĐỒ CĂN LỀ & DÙNG TAB STOP CHUYÊN NGHIỆP
            text_length = len(full_text_clean)
            target_align = default_align
            target_indent = default_indent
            is_signature_block = False
            
            if text_length > 0 and text_length < 60:
                if leading_spaces_count >= 15:
                    is_signature_block = True
                    target_align = "left"    # Đặt lề trái, đẩy chữ bằng Tab Stop
                    target_indent = "0"
                elif 6 <= leading_spaces_count < 15:
                    target_align = "center"  # Tiêu đề phụ căn giữa
                    target_indent = "0"

            if drawings:
                target_indent = "0"
                target_align = "center"

            # 5. ĐỔ KHUÔN ĐỊNH DẠNG VÀO XML
            pPr = p.find('w:pPr', namespaces=self.namespaces)
            if pPr is None:
                pPr = etree.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
                p.insert(0, pPr)

            jc = pPr.find('w:jc', namespaces=self.namespaces)
            if jc is None:
                jc = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}jc')
            jc.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', target_align)

            # Xử lý Lùi đầu dòng
            ind = pPr.find('w:ind', namespaces=self.namespaces)
            if ind is None:
                ind = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ind')
            for attr in ['left', 'right', 'hanging', 'firstLine']:
                full_attr = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}' + attr
                if full_attr in ind.attrib:
                    del ind.attrib[full_attr]
            if target_indent != "0":
                ind.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}firstLine', target_indent)

            # === CƠ CHẾ TAB STOP CHUYÊN NGHIỆP ===
            if is_signature_block:
                # Thiết lập mốc Tab ở vị trí 13.5cm (khoảng 7650 twips) - Căn giữa mốc đó
                tabs = pPr.find('w:tabs', namespaces=self.namespaces)
                if tabs is not None:
                    pPr.remove(tabs)
                tabs = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tabs')
                tab_stop = etree.SubElement(tabs, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tab')
                tab_stop.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 'center')
                tab_stop.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pos', '7650')

                # Tự động chèn 1 phím Tab vào thẻ <w:r> đầu tiên có chứa chữ
                runs = p.xpath('.//w:r', namespaces=self.namespaces)
                for r in runs:
                    t_nodes = r.xpath('.//w:t', namespaces=self.namespaces)
                    if t_nodes and t_nodes[0].text and t_nodes[0].text.strip():
                        # Chèn thẻ <w:tab/> vào trước thẻ <w:t>
                        tab_elem = etree.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tab')
                        t_nodes[0].addprevious(tab_elem)
                        break

            # Ép Giãn dòng & Cách đoạn chuẩn HUST
            spacing = pPr.find('w:spacing', namespaces=self.namespaces)
            if spacing is None:
                spacing = etree.SubElement(pPr, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}spacing')
            spacing.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}line', line_val)
            spacing.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}lineRule', 'auto')
            spacing.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}before', space_val) 
            spacing.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}after', space_val)  

        return tree