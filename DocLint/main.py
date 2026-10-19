"""CLI sharing the same V1 analysis, rules, rendering and integrity pipeline."""

import argparse
import hashlib
import json
from pathlib import Path
from v1.analysis import analyze_document
from v1.pipeline import format_document


def load_profile(profile_path):
    return json.loads(Path(profile_path).read_text(encoding="utf-8"))


def run_system_test(docx_path, profile_path=None, output_path=None):
    if profile_path is not None:
        from core.profiles import HUST

        supplied = load_profile(profile_path)
        if any(
            supplied.get(key) != HUST[key]
            for key in ("margin_rules", "typography", "paragraph_rules")
        ):
            raise ValueError("Chỉ hỗ trợ mẫu HUST đã đăng ký cho lời gọi tương thích.")
    if output_path is None:
        raise ValueError("Cần chỉ định tệp đầu ra khác tệp gốc.")
    source, output = Path(docx_path), Path(output_path)
    if source.resolve() == output.resolve():
        raise ValueError("Không được ghi đè tệp gốc.")
    result, report = format_document(source.read_bytes())
    output.write_bytes(result)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(
        description="DocLint V1: phân tích và dàn trang báo cáo, không gọi AI."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Chỉ phân tích, in JSON để duyệt cấu trúc.",
    )
    parser.add_argument("--profile", choices=["hust", "report"])
    parser.add_argument(
        "--options", type=Path, help="JSON lựa chọn hoặc nhật ký có trường options."
    )
    parser.add_argument(
        "--preview-dir",
        type=Path,
        help="Thư mục riêng lưu PDF và bản Word đã đối chiếu.",
    )
    args = parser.parse_args()
    data = args.input.read_bytes()
    if args.analyze:
        print(json.dumps(analyze_document(data), ensure_ascii=False, indent=2))
        return
    if args.output is None:
        parser.error("Cần chỉ định tệp đầu ra hoặc --analyze.")
    if args.input.resolve() == args.output.resolve():
        parser.error("Tệp đầu ra phải khác tệp gốc.")
    options = {}
    if args.options:
        record = json.loads(args.options.read_text(encoding="utf-8"))
        expected_hash = record.get("integrity", {}).get("source_sha256")
        if expected_hash and expected_hash != hashlib.sha256(data).hexdigest():
            parser.error(
                "Nhật ký lựa chọn không thuộc tệp gốc này; hãy phân tích và duyệt lại."
            )
        options = record.get("options", record)
    if args.profile:
        options["profile"] = args.profile
    result, report = format_document(data, options, args.preview_dir)
    args.output.write_bytes(result)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
