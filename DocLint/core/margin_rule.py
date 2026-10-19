from core.base_rule import BaseRule

class MarginRule(BaseRule):
    def check(self, tree, namespaces):
        issues = []
        expected_left = self.profile["margin_rules"]["left"]
        expected_right = self.profile["margin_rules"]["right"]
        
        # Nhắm thẳng tọa độ thẻ lề trang
        pg_mar_tags = tree.xpath('.//w:sectPr/w:pgMar', namespaces=namespaces)
        
        for pg_mar in pg_mar_tags:
            left = pg_mar.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}left')
            right = pg_mar.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}right')
            
            # Đối chiếu và ghi nhận lỗi
            if left != expected_left:
                issues.append(f"LỖI R1: Sai lề trái (Hiện tại: {left} -> Chuẩn: {expected_left})")
            if right != expected_right:
                issues.append(f"LỖI R1: Sai lề phải (Hiện tại: {right} -> Chuẩn: {expected_right})")
                
        return issues