import zipfile
import json
from lxml import etree

from core.inspector import DocInspector
from core.autofix import DocFixer

def load_profile(profile_path):
    with open(profile_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_system_test(docx_path, profile_path, output_path):
    print(f"🚀 KÍCH HOẠT HỆ THỐNG DOCLINT...\n")
    try:
        profile = load_profile(profile_path)
        inspector = DocInspector(profile)
        
        with zipfile.ZipFile(docx_path, 'r') as docx_zip:
            # Bóc tách cả Nội dung VÀ Giao diện gốc
            xml_content = docx_zip.read('word/document.xml')
            tree = etree.fromstring(xml_content)
            
            styles_content = docx_zip.read('word/styles.xml')
            styles_tree = etree.fromstring(styles_content)
            
        issues = inspector.inspect(tree)
        
        print("📊 BÁO CÁO CHẨN ĐOÁN LỖI:")
        print("="*40)
        if issues:
            for index, issue in enumerate(issues, 1):
                print(f" {index}. {issue}")
                
        print("\n🔧 Kích hoạt Động cơ Auto-Fix...")
        fixer = DocFixer(profile)
        
        # 1. Chữa lành cấu trúc nội dung
        fixed_tree = fixer.fix_margins(tree)
        fixed_tree = fixer.fix_fonts(fixed_tree)
        fixed_tree = fixer.fix_fake_headings(fixed_tree)
        fixed_tree = fixer.fix_paragraphs(fixed_tree)
        # 2. Đánh sập và ghi đè Trụ sở Style gốc
        fixed_styles_tree = fixer.fix_global_styles(styles_tree)
        
        print(f"📦 Đang đóng gói tệp Word mới: {output_path}")
        
        # 3. Tráo đổi và nén tệp lại
        with zipfile.ZipFile(docx_path, 'r') as zin:
            with zipfile.ZipFile(output_path, 'w') as zout:
                for item in zin.infolist():
                    if item.filename == 'word/document.xml':
                        xml_bytes = etree.tostring(fixed_tree, xml_declaration=True, encoding='UTF-8', standalone='yes')
                        zout.writestr(item, xml_bytes)
                    elif item.filename == 'word/styles.xml':
                        styles_bytes = etree.tostring(fixed_styles_tree, xml_declaration=True, encoding='UTF-8', standalone='yes')
                        zout.writestr(item, styles_bytes)
                    else:
                        zout.writestr(item, zin.read(item.filename))
                        
        print("🎉 Hoàn tất! Lề và Font chữ đã được đồng bộ 100%.")
            
    except Exception as e:
        print(f"❌ Hệ thống gặp sự cố: {e}")

if __name__ == "__main__":
    run_system_test("test_input.docx", "profiles/hust_standard.json", "test_output_fixed.docx")