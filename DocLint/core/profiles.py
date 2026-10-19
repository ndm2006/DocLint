"""Reviewed application presets; these are not institutional certification."""
from copy import deepcopy
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
HUST = json.loads((BASE / 'profiles/hust_standard.json').read_text(encoding='utf-8'))
HUST['page_rules'] = {'w': '11906', 'h': '16838', 'orient': 'portrait'}
REPORT = deepcopy(HUST)
REPORT.update(profile_name='Báo cáo gọn gàng')
REPORT['margin_rules'] = {'left': '1417', 'right': '1417', 'top': '1134', 'bottom': '1134'}
REPORT['typography'].update(default_font='Calibri', default_size='24')
REPORT['paragraph_rules'].update(line_spacing='288', first_line_indent='0', space_before='0', space_after='160')
PROFILES = {'hust': HUST, 'report': REPORT}

DESCRIPTIONS = {
    'hust': {'name': 'Báo cáo học thuật · HUST', 'description': 'Theo cấu hình HUST của dự án; hãy đối chiếu yêu cầu riêng của khoa.', 'font': 'Times New Roman', 'font_size': '13 pt', 'line_spacing': '1,5 dòng', 'margins': 'Trái 3 · phải 2 · trên 2 · dưới 2 cm'},
    'report': {'name': 'Báo cáo gọn gàng', 'description': 'Mẫu trình bày phổ thông, thoáng và dễ đọc.', 'font': 'Calibri', 'font_size': '12 pt', 'line_spacing': '1,2 dòng', 'margins': 'Trái/phải 2,5 · trên/dưới 2 cm'},
}

def get_profile(profile_id):
    if profile_id not in PROFILES:
        raise ValueError('Mẫu định dạng không được hỗ trợ.')
    return deepcopy(PROFILES[profile_id])
