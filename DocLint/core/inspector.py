from core.margin_rule import MarginRule
from core.font_rule import FontRule
from core.heading_rule import HeadingRule

class DocInspector:
    def __init__(self, profile):
        self.profile = profile
        self.namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        # Tuyển dụng các chuyên gia vào đội kiểm tra
        self.rules = [
            MarginRule(profile),
            FontRule(profile),
            HeadingRule(profile)
        ]

    def inspect(self, tree):
        all_issues = []
        
        # Lần lượt cho từng chuyên gia khám bệnh tệp Word
        for rule in self.rules:
            issues = rule.check(tree, self.namespaces)
            if issues:
                all_issues.extend(issues)
                
        return all_issues