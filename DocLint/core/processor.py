"""Bounded DOCX processing with an independent content-integrity gate."""
from collections import Counter
from copy import copy, deepcopy
from dataclasses import dataclass
from io import BytesIO
import zipfile
from lxml import etree
from core.autofix import DocFixer
from core.profiles import get_profile
from core.xmlutils import NS, q, parse_xml, content_signature

MAX_UPLOAD = 15 * 1024 * 1024
MAX_EXPANDED = 80 * 1024 * 1024
MAX_XML = 8 * 1024 * 1024
MAX_ENTRIES = 2000

class DocumentError(ValueError):
    pass

@dataclass
class ProcessedDocument:
    data: bytes
    report: dict

LABELS = {
    'margins': 'Lề trang', 'page_size': 'Khổ giấy A4', 'fonts': 'Phông chữ phần thân bài',
    'font_size': 'Cỡ chữ phần thân bài', 'default_font': 'Phông chữ mặc định',
    'paragraphs': 'Căn lề, giãn dòng và cách đoạn', 'images': 'Căn giữa ảnh trong dòng',
}
WARNING_TEXT = {
    'headings': ('Tiêu đề cần xem lại', 'Có đoạn giống tiêu đề nhưng chưa đủ căn cứ để tự gán cấp Heading. Cấu trúc tiêu đề được giữ nguyên.'),
    'manual_spacing': ('Căn lề bằng ký tự', 'Có đoạn dùng khoảng trắng đầu dòng hoặc Tab. Ký tự và vị trí trình bày được giữ nguyên để bạn kiểm tra.'),
    'complex_sections': ('Bố cục trang đặc biệt', 'Trang ngang hoặc nhiều cột được giữ nguyên khổ giấy và lề, tránh làm vỡ bố cục.'),
    'symbol_fonts': ('Phông ký hiệu chuyên dụng', 'Giữ nguyên phông ký hiệu để không đổi hình dạng hoặc ý nghĩa của ký tự.'),
}

def _open(data):
    if not data or len(data) > MAX_UPLOAD:
        raise DocumentError('Tệp phải có dung lượng từ 1 byte đến 15 MB.')
    try:
        archive = zipfile.ZipFile(BytesIO(data))
        infos = archive.infolist()
        names = [i.filename for i in infos]
        if len(infos) > MAX_ENTRIES or len(names) != len(set(names)):
            raise DocumentError('Gói DOCX có quá nhiều mục hoặc mục trùng tên.')
        if sum(i.file_size for i in infos) > MAX_EXPANDED:
            raise DocumentError('Dung lượng giải nén của tài liệu vượt 80 MB.')
        for i in infos:
            if i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise DocumentError('Kiểu nén ZIP của tài liệu chưa được hỗ trợ.')
            if i.flag_bits & 1:
                raise DocumentError('Chưa hỗ trợ tài liệu được mã hóa hoặc có mật khẩu.')
            if i.filename.startswith(('/', '\\')) or '..' in i.filename.replace('\\', '/').split('/'):
                raise DocumentError('Cấu trúc đường dẫn trong tài liệu không hợp lệ.')
            if i.file_size > MAX_XML and i.filename.lower().endswith('.xml'):
                raise DocumentError('Một phần XML vượt giới hạn 8 MB.')
        if any('vbaproject' in n.lower() or n.lower().startswith('_xmlsignatures/') for n in names):
            raise DocumentError('Chưa hỗ trợ tài liệu có macro hoặc chữ ký số.')
        required = {'[Content_Types].xml', '_rels/.rels', 'word/document.xml', 'word/styles.xml'}
        if not required.issubset(names):
            raise DocumentError('Thiếu thành phần DOCX bắt buộc (nội dung, styles hoặc quan hệ).')
        if archive.testzip() is not None:
            raise DocumentError('Một thành phần trong tệp DOCX đã hỏng dữ liệu.')
        content_types = parse_xml(archive.read('[Content_Types].xml'))
        main_type = content_types.xpath('//*[local-name()="Override"][@PartName="/word/document.xml"]/@ContentType')
        if main_type != ['application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml']:
            raise DocumentError('Tệp không phải tài liệu Word DOCX tiêu chuẩn.')
        document = parse_xml(archive.read('word/document.xml'))
        styles = parse_xml(archive.read('word/styles.xml'))
        if document.tag != q('document') or document.find(q('body')) is None or styles.tag != q('styles'):
            raise DocumentError('Cấu trúc WordprocessingML không hợp lệ hoặc chưa được hỗ trợ.')
        return archive, document, styles
    except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError, RuntimeError, NotImplementedError, OverflowError) as e:
        raise DocumentError('Không đọc được cấu trúc DOCX. Hãy mở và lưu lại bằng Word rồi thử lại.') from e
    except ValueError as e:
        if isinstance(e, DocumentError):
            raise
        raise DocumentError(str(e)) from e


def process_document(data, profile_id='hust'):
    profile = get_profile(profile_id)
    archive, original, original_styles = _open(data)
    with archive:
        tree, styles = deepcopy(original), deepcopy(original_styles)
        fixer = DocFixer(profile, styles)
        try:
            fixer.fix_margins(tree)
            fixer.fix_fonts(tree)
            fixer.fix_paragraphs(tree)
            fixer.fix_global_styles(styles)
            if content_signature(original) != content_signature(tree) or content_signature(original_styles) != content_signature(styles):
                raise DocumentError('Không thể xác nhận tính toàn vẹn. Hệ thống đã dừng và không xuất tài liệu.')
        except (ValueError, TypeError, etree.LxmlError) as e:
            if isinstance(e, DocumentError):
                raise
            raise DocumentError('Tài liệu có thuộc tính bố cục không hợp lệ hoặc chưa được hỗ trợ.') from e
        warnings = []
        # Analyze once to count paragraphs, rather than counting each fix pass.
        analyzer = DocFixer(profile, original_styles)
        list(analyzer.body_paragraphs(original))
        counts = Counter(analyzer.warnings)
        counts['complex_sections'] = fixer.warnings['complex_sections']
        counts['symbol_fonts'] = fixer.warnings['symbol_fonts']
        for code, count in counts.items():
            if count:
                title, description = WARNING_TEXT[code]
                warnings.append({'code': code, 'title': title, 'description': description, 'count': count})
        tables = tree.xpath('.//w:tbl', namespaces=NS)
        if tables:
            warnings.append({'code': 'tables', 'title': 'Bảng biểu được bảo toàn', 'description': 'Giữ nguyên độ rộng cột, ô gộp và nội dung bảng. Cần xem lại bảng rộng trong Word sau khi đổi lề trang.', 'count': len(tables)})
        drawings = tree.xpath('.//w:drawing | .//w:pict', namespaces=NS)
        if drawings:
            warnings.append({'code': 'visual_review', 'title': 'Kiểm tra ngắt trang trong Word', 'description': 'Ảnh, công thức và đối tượng được giữ nguyên. Số trang và vị trí ngắt trang cần kiểm tra trong Word; trình duyệt không mô phỏng bộ dàn trang Word.', 'count': len(drawings)})
        # All untouched ZIP members must survive byte-for-byte.
        updated = {
            'word/document.xml': etree.tostring(tree, encoding='UTF-8', xml_declaration=True, standalone=True),
            'word/styles.xml': etree.tostring(styles, encoding='UTF-8', xml_declaration=True, standalone=True),
        }
        result = BytesIO()
        with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED) as out:
            out.comment = archive.comment
            for info in archive.infolist():
                out.writestr(copy(info), updated[info.filename] if info.filename in updated else archive.read(info.filename))
        output = result.getvalue()
        with zipfile.ZipFile(BytesIO(output)) as verified:
            if verified.namelist() != archive.namelist():
                raise DocumentError('Kiểm tra thành phần tài liệu không thành công.')
            for name in archive.namelist():
                if name not in updated and archive.read(name) != verified.read(name):
                    raise DocumentError('Kiểm tra dữ liệu đính kèm không thành công.')
            for name, old in [('word/document.xml', original), ('word/styles.xml', original_styles)]:
                if content_signature(old) != content_signature(parse_xml(verified.read(name))):
                    raise DocumentError('Kiểm tra nội dung sau đóng gói không thành công.')
        verification = DocFixer(profile, styles)
        audit_tree, audit_styles = deepcopy(tree), deepcopy(styles)
        verification.fix_margins(audit_tree)
        verification.fix_fonts(audit_tree)
        verification.fix_paragraphs(audit_tree)
        verification.fix_global_styles(audit_styles)
        if sum(verification.changes.values()):
            raise DocumentError('Định dạng chưa ổn định sau chuẩn hóa; không xuất kết quả.')
        total = sum(fixer.checks.values())
        verified_checks = sum(verification.checks.values())
        verified_changes = sum(verification.changes.values())
        changed = sum(fixer.changes.values())
        report = {
            'profile': profile_id,
            'score': {'before': round(100 * (total - changed) / total) if total else 100,
                      'after': round(100 * (verified_checks - verified_changes) / verified_checks) if verified_checks else 100,
                      'scope': 'Tỷ lệ thuộc tính khớp mẫu trong phạm vi tự động chuẩn hóa; không đánh giá toàn bộ bố cục hay nội dung.'},
            'changes': [{'code': k, 'title': LABELS[k], 'count': v} for k, v in fixer.changes.items() if v],
            'warnings': warnings,
            'summary': {'changed_properties': changed, 'checked_properties': total,
                        'paragraphs': len(tree.xpath('.//w:p', namespaces=NS)), 'tables': len(tables),
                        'images': len(drawings), 'equations': len(tree.xpath('.//m:oMath', namespaces=NS))},
            'integrity': {'verified': True, 'method': 'So sánh cấu trúc XML ngoài các thuộc tính trình bày cho phép và đối chiếu từng thành phần còn lại của gói DOCX.'},
        }
        return ProcessedDocument(output, report)
