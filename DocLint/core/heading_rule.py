import re
from core.base_rule import BaseRule

class HeadingRule(BaseRule):
    def check(self, tree, namespaces):
        issues = []
        # Bộ lọc Regex: Bắt các chuỗi bắt đầu bằng "Chương X", "I.", "1.", "1.1."
        heading_pattern = re.compile(r'^((Chương|Chapter|Phần|Part|Bài|Section)\s*(?:\d+|[IVX]+)|[IVX]+\.|[0-9]+(\.[0-9]+)*\.*)', re.IGNORECASE)
        
        # Tìm tất cả các đoạn văn (<w:p>)
        paragraphs = tree.xpath('.//w:p', namespaces=namespaces)
        
        for p in paragraphs:
            # Nếu đoạn văn có chứa thẻ in đậm (<w:b/>)
            bolds = p.xpath('.//w:rPr/w:b', namespaces=namespaces)
            if bolds:
                # Rút trích toàn bộ chữ (text) của đoạn văn đó
                texts = p.xpath('.//w:t/text()', namespaces=namespaces)
                full_text = "".join(texts).strip()
                
                # Suy đoán 1: Cấu trúc giống tiêu đề và ngắn (< 100 ký tự)
                if full_text and len(full_text) < 100 and heading_pattern.match(full_text):
                                    
                     # Suy đoán 2: Không phải là một câu văn kể lể kết thúc bằng dấu câu
                    if not full_text.endswith(('.', '?', '!')):
                        # Kiểm tra xem nó đã được bọc Heading chuẩn chưa
                        pStyle = p.xpath('.//w:pPr/w:pStyle/@w:val', namespaces=namespaces)
                        if not pStyle or 'Heading' not in pStyle[0]:
                            issues.append(f"LỖI P3: Tiêu đề giả phát hiện - '{full_text[:30]}...' đang dùng in đậm thủ công.")
                        
        return issues