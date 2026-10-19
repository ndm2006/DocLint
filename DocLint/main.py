"""CLI and backwards-compatible function sharing the exact same web engine."""
import argparse
import json
from pathlib import Path
from core.processor import process_document


def load_profile(profile_path):
    return json.loads(Path(profile_path).read_text(encoding='utf-8'))


def run_system_test(docx_path, profile_path=None, output_path=None):
    # Legacy callers can still supply the existing HUST profile path.
    if profile_path is not None:
        from core.profiles import HUST
        supplied = load_profile(profile_path)
        if any(supplied.get(k) != HUST[k] for k in ('margin_rules', 'typography', 'paragraph_rules')):
            raise ValueError('Dùng các mẫu đã đăng ký trong core/profiles.py.')
    if output_path is None:
        raise ValueError('Cần chỉ định tệp đầu ra khác tệp gốc.')
    source, output = Path(docx_path), Path(output_path)
    if source.resolve() == output.resolve():
        raise ValueError('Không được ghi đè tệp gốc.')
    processed = process_document(source.read_bytes())
    output.write_bytes(processed.data)
    print(json.dumps(processed.report, ensure_ascii=False, indent=2))
    return processed.report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Chuẩn hóa định dạng DOCX, giữ nguyên nội dung.')
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--profile', choices=['hust', 'report'], default='hust')
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Tệp đầu ra phải khác tệp gốc.')
    result = process_document(args.input.read_bytes(), args.profile)
    args.output.write_bytes(result.data)
    print(json.dumps(result.report, ensure_ascii=False, indent=2))
