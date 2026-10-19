class BaseRule:
    def __init__(self, profile):
        # Nạp bộ luật (hust_standard.json) vào trí nhớ của chuyên gia
        self.profile = profile

    def check(self, tree, namespaces):
        # Hàm này sẽ được viết chi tiết ở từng chuyên gia cụ thể
        pass