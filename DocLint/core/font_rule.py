from core.base_rule import BaseRule

class FontRule(BaseRule):
    def check(self, tree, namespaces):
        issues = []
        expected_font = self.profile["typography"]["default_font"]
        
        # Truy vấn XPath tìm tất cả các thẻ font bị gán thủ công
        font_tags = tree.xpath('.//w:rPr/w:rFonts', namespaces=namespaces)
        bad_fonts = set()
        
        for font_tag in font_tags:
            # Lấy tên font chữ đang được sử dụng
            ascii_font = font_tag.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii')
            
            if ascii_font and ascii_font != expected_font:
                bad_fonts.add(ascii_font)
        
        if bad_fonts:
            issues.append(f"LỖI R3: Tệp bị lẫn rác định dạng font cục bộ {list(bad_fonts)}. Chuẩn bắt buộc: {expected_font}")
            
        return issues