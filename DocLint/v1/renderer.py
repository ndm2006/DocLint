"""Local-only LibreOffice previews and bounded PDFium inspection.

No DOCX returned by LibreOffice is adopted as the user's output. The original
OpenXML engine remains authoritative; the renderer produces PDF only.
"""

from contextlib import closing, contextmanager
from copy import copy
from functools import wraps
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
import warnings
from PIL import Image
import pypdfium2 as pdfium
from lxml import etree
from core.xmlutils import NS, q, parse_xml
from v1.analysis import plain
from v1.diagnostics import record_failure

PDF_LOCK = threading.RLock()  # PDFium is not thread-safe.
MAX_PAGES = 120
RENDER_TIMEOUT = 60


class PreviewError(RuntimeError):
    def __init__(self, message, diagnostic=None):
        super().__init__(message)
        self.diagnostic = diagnostic


def _preview_guard(phase):
    def decorate(operation):
        @wraps(operation)
        def guarded(*args, **kwargs):
            try:
                return operation(*args, **kwargs)
            except PreviewError:
                raise
            except Exception as exc:
                detail = record_failure(exc, phase)
                raise PreviewError(
                    "Bộ xem trước gặp lỗi; bạn vẫn có thể duyệt và xử lý Word. "
                    f"Mã chẩn đoán: {detail['reference']}.",
                    diagnostic=detail,
                ) from None

        return guarded

    return decorate


def _console_office(path):
    candidate = Path(path)
    if sys.platform == "win32" and candidate.name.lower() == "soffice.exe":
        console = candidate.with_suffix(".com")
        if console.is_file():
            return str(console)
    return str(candidate)


def find_office():
    configured = os.environ.get("DOCLINT_SOFFICE")
    if configured:
        return _console_office(configured) if Path(configured).is_file() else None
    names = (
        ("soffice.com", "soffice.exe", "libreoffice")
        if sys.platform == "win32"
        else ("soffice", "libreoffice")
    )
    for name in names:
        found = shutil.which(name)
        if found:
            return _console_office(found)
    if sys.platform == "win32":
        for base in (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
        ):
            if base:
                candidate = Path(base) / "LibreOffice" / "program" / "soffice.exe"
                if candidate.is_file():
                    return _console_office(candidate)
    return None


def capabilities():
    return {
        "renderer": bool(find_office()),
        "engine": "LibreOffice → PDFium",
        "max_pages": MAX_PAGES,
        "ai_api": False,
        "message": "Có bộ dựng PDF cục bộ."
        if find_office()
        else "Cài LibreOffice để dùng xem trước–sau, cập nhật trang mục lục và kiểm tra bố cục.",
    }


def validate_svg(raw):
    if len(raw) > 8 * 1024 * 1024:
        raise PreviewError("Ảnh SVG vượt hạn mức XML 8 MB.")
    try:
        root = parse_xml(raw)
    except (ValueError, etree.LxmlError):
        raise PreviewError("SVG có DTD hoặc cấu trúc không được hỗ trợ.") from None
    if root.tag != "{http://www.w3.org/2000/svg}svg" or root.getroottree().xpath(
        "//processing-instruction()"
    ):
        raise PreviewError("SVG có cấu trúc hoặc chỉ thị ngoài chưa được hỗ trợ.")
    active = {
        "script",
        "foreignobject",
        "iframe",
        "object",
        "embed",
        "image",
        "audio",
        "video",
        "animate",
        "set",
        "animation",
    }
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if etree.QName(node).localname.casefold() in active:
            raise PreviewError(
                "SVG chứa thành phần chủ động/ảnh lồng; không dựng trên máy chủ."
            )
        css = (
            [node.text or ""]
            if etree.QName(node).localname.casefold() == "style"
            else []
        )
        for key, value in node.attrib.items():
            name = etree.QName(key).localname.casefold()
            if name.startswith("on") or (
                name in {"href", "src", "base"} and value and not value.startswith("#")
            ):
                raise PreviewError(
                    "SVG có sự kiện hoặc tham chiếu ngoài; không dựng trên máy chủ."
                )
            if name == "style" or "url" in value.casefold():
                css.append(value)
        for value in css:
            stripped = re.sub(
                r"url\(\s*['\"]?#[A-Za-z0-9_.:-]{1,256}['\"]?\s*\)",
                "",
                value,
                flags=re.I,
            )
            if "url" in stripped.casefold() or "@" in stripped or chr(92) in stripped:
                raise PreviewError(
                    "SVG có CSS nạp tài nguyên hoặc cú pháp chưa được hỗ trợ."
                )


def _safe_preview_copy(data):
    """Disable external relationships and active fields in the preview copy only.

    Public deployments must additionally use the supplied isolated container
    network. Unsupported active/embedded objects are never handed to Office.
    """
    out = BytesIO()
    with (
        zipfile.ZipFile(BytesIO(data)) as src,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        total_pixels = 0
        for info in src.infolist():
            raw = src.read(info.filename)
            name = info.filename.lower()
            if any(part in name for part in ("/embeddings/", "/activex/")):
                raise PreviewError(
                    "Không dựng tệp có đối tượng nhúng/ActiveX; DOCX vẫn được bảo toàn để xem bằng Word."
                )
            if name.startswith("word/media/") and name.endswith(
                (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp")
            ):
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", Image.DecompressionBombWarning)
                        with Image.open(BytesIO(raw)) as image:
                            pixels = image.width * image.height
                    total_pixels += pixels
                    if pixels > 40_000_000 or total_pixels > 80_000_000:
                        raise PreviewError(
                            "Ảnh vượt hạn mức dựng (40 triệu điểm ảnh/mỗi ảnh, 80 triệu điểm ảnh/tệp). DOCX vẫn được giữ để xem bằng Word."
                        )
                except (Image.DecompressionBombWarning, Image.DecompressionBombError):
                    raise PreviewError(
                        "Kích thước giải mã ảnh quá lớn để dựng an toàn."
                    ) from None
                except OSError:
                    raise PreviewError(
                        "Một ảnh trong tài liệu không đọc được; chưa dựng PDF."
                    ) from None
            if name.endswith(".svg"):
                validate_svg(raw)
            if name.endswith(".rels"):
                root = parse_xml(raw)
                for rel in root:
                    if rel.get("TargetMode") == "External":
                        if not rel.get("Type", "").endswith("/hyperlink"):
                            raise PreviewError(
                                "Tài liệu phụ thuộc ảnh, mẫu hoặc tài nguyên ngoài; máy chủ không tải tài nguyên đó nên chưa dựng PDF."
                            )
                        rel.set("Target", "about:blank")
                raw = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True
                )
            elif name.startswith("word/") and name.endswith(".xml"):
                root = parse_xml(raw)
                if root.xpath(
                    ".//w:altChunk | .//w:object | .//w:subDoc", namespaces=NS
                ):
                    raise PreviewError(
                        "Tệp có nội dung nhúng chưa được hỗ trợ dựng an toàn; hãy kiểm tra bằng Word."
                    )
                instructions = root.xpath(
                    ".//w:instrText/text() | .//w:fldSimple/@w:instr", namespaces=NS
                )
                if any(
                    re.search(
                        r"\b(?:DDE|DDEAUTO|INCLUDETEXT|INCLUDEPICTURE|DATABASE|LINK)\b",
                        text,
                        re.I,
                    )
                    for text in instructions
                ):
                    raise PreviewError(
                        "Tệp có trường nạp dữ liệu ngoài; không dựng trên máy chủ."
                    )
                # Do not let Office silently refresh our cached TOC during PDF
                # generation; page numbers are reconciled in a bounded pass.
                for node in root.xpath(".//w:updateFields", namespaces=NS):
                    node.set(q("val"), "false")
                raw = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True
                )
            target.writestr(copy(info), raw)
    return out.getvalue()


def _office_environment(scratch):
    env = {
        key: os.environ[key]
        for key in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "LANG",
            "LC_ALL",
            "FONTCONFIG_FILE",
            "FONTCONFIG_PATH",
        )
        if key in os.environ
    }
    env.update(
        TMPDIR=str(scratch),
        TMP=str(scratch),
        TEMP=str(scratch),
        XDG_CACHE_HOME=str(scratch / "cache"),
        SAL_USE_VCLPLUGIN="svp",
    )
    # Isolate Office's writable user directories while supplying the Windows
    # variables it needs. Never inherit API credentials or HTTP proxies.
    private_directories = {"HOME": scratch / "home"}
    if sys.platform == "win32":
        private_directories.update(
            USERPROFILE=scratch / "home",
            APPDATA=scratch / "a",
            LOCALAPPDATA=scratch / "l",
        )
    for key, directory in private_directories.items():
        directory.mkdir(parents=True, exist_ok=True)
        env[key] = str(directory)
    return env


def cleanup_office_workspaces(parent):
    """Retry only our private scratch folders, after the job stops rendering."""
    for folder in Path(parent).glob("office-*"):
        if folder.is_dir() and not folder.is_symlink():
            try:
                shutil.rmtree(folder)
            except OSError:
                pass  # Retained inside the private session; retry on the next sweep.


@contextmanager
def _office_workspace(parent):
    try:
        scratch = Path(tempfile.mkdtemp(prefix="office-", dir=parent))
    except OSError as exc:
        detail = record_failure(exc, "office_workspace_create")
        raise PreviewError(
            "Không tạo được thư mục tạm cho LibreOffice. "
            f"Mã chẩn đoán: {detail['reference']}.",
            detail,
        ) from None
    try:
        yield scratch
    finally:
        # Windows can briefly retain Office/antivirus handles after conversion.
        # A cleanup failure must not invalidate an already verified PDF or mask
        # the original render error. The session janitor will retry this folder.
        for attempt in range(3):
            try:
                shutil.rmtree(scratch)
                break
            except FileNotFoundError:
                break
            except OSError as exc:
                if attempt == 2:
                    record_failure(exc, "office_workspace_cleanup")
                else:
                    time.sleep(0.05)


@_preview_guard("render_pdf")
def render_pdf(data, destination, cancel=None, timeout=RENDER_TIMEOUT):
    executable = find_office()
    if not executable:
        raise PreviewError(capabilities()["message"])
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe = _safe_preview_copy(data)
    with _office_workspace(destination.parent) as scratch:
        input_path = scratch / "document.docx"
        input_path.write_bytes(safe)
        profile = scratch / "p"
        (profile / "user").mkdir(parents=True)
        (profile / "user" / "registrymodifications.xcu").write_text(
            '<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
            '<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>'
            '<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item>'
            "</oor:items>",
            encoding="utf-8",
        )
        env = _office_environment(scratch)
        args = [
            executable,
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--norestore",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(scratch),
            str(input_path),
        ]
        kwargs = (
            {"start_new_session": True}
            if os.name != "nt"
            else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        )
        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                **kwargs,
            )
        except OSError:
            raise PreviewError(
                "Không khởi động được LibreOffice. Kiểm tra cài đặt hoặc biến DOCLINT_SOFFICE."
            ) from None
        started = time.monotonic()
        try:
            while True:
                try:
                    process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    if (
                        cancel is not None and cancel.is_set()
                    ) or time.monotonic() - started > timeout:
                        raise PreviewError(
                            "Đã hủy công việc hoặc bộ dựng vượt thời gian 60 giây."
                        )
            converted = scratch / "document.pdf"
            if (
                process.returncode
                or not converted.is_file()
                or converted.stat().st_size == 0
            ):
                raise PreviewError(
                    "LibreOffice chưa dựng được tài liệu. Hãy mở bản DOCX bằng Word để xem lại."
                )
            with PDF_LOCK, closing(pdfium.PdfDocument(converted)) as pdf:
                if len(pdf) > MAX_PAGES:
                    raise PreviewError(
                        f"Bản xem trước vượt giới hạn {MAX_PAGES} trang."
                    )
                if not len(pdf):
                    raise PreviewError("Bộ dựng trả về PDF không có trang.")
            temporary = destination.with_suffix(".pending.pdf")
            shutil.copyfile(converted, temporary)
            temporary.replace(destination)
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate()


def extract_page_label(footer):
    found = None
    pattern = re.compile(
        r"^\s*(?:(?:trang|page)\s+)?(\d+|[ivxlcdm]+)(?:\s*(?:/|of|trong|trên)\s*\d+)?\s*$",
        re.I,
    )
    for line in footer.splitlines():
        match = pattern.fullmatch(line.strip())
        if match:
            found = match.group(1)
    return found


@_preview_guard("inspect_pdf")
def inspect_pdf(path, headings=(), blocks=(), section_bounds=None):
    pages = []
    warnings = []
    with PDF_LOCK, closing(pdfium.PdfDocument(path)) as pdf:
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            text = plain(textpage.get_text_bounded())
            width, height = page.get_size()
            footer = textpage.get_text_bounded(left=0, bottom=0, right=width, top=65)
            label = extract_page_label(footer)
            rects = []
            for ri in range(min(textpage.count_rects(), 10000)):
                rects.append(list(textpage.get_rect(ri)))
            for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
                rects.append(list(obj.get_bounds()))
            pages.append(
                {
                    "number": index + 1,
                    "width": round(width, 1),
                    "height": round(height, 1),
                    "text_chars": len(text),
                    "label": label,
                    "_text": text,
                    "_rects": rects,
                }
            )
            # Low text can be a figure page: informational, never auto-delete.
            if len(text) < 30:
                warnings.append(
                    {
                        "code": "sparse_page",
                        "page": index + 1,
                        "title": "Trang ít chữ cần xem lại",
                        "description": "Có thể là bìa, trang hình hoặc trang trống có chủ đích. Hệ thống không tự xóa.",
                    }
                )
            textpage.close()
            page.close()
        locations = {}
        ceiling = len(pages)
        for heading in reversed(list(headings)):
            needle = plain(heading["text"])
            matches = [
                p["number"]
                for p in pages
                if needle and needle in p["_text"] and p["number"] <= ceiling
            ]
            if not matches:
                continue
            number = max(matches)  # Prefer body occurrence over generated TOC.
            ceiling = number
            page = pdf[number - 1]
            textpage = page.get_textpage()
            search = textpage.search(heading["text"])
            match = search.get_next()
            rect = None
            if match:
                count = textpage.count_rects(*match)
                if count:
                    rect = textpage.get_rect(0)
            if rect and rect[1] < 90:
                warnings.append(
                    {
                        "code": "heading_low",
                        "page": number,
                        "block_id": heading["id"],
                        "title": "Tiêu đề gần cuối trang",
                        "description": "Hãy kiểm tra phần nội dung đi cùng tiêu đề; không tự thay chữ hoặc giảm cỡ chữ.",
                    }
                )
            locations[heading["id"]] = {
                "page": number,
                "label": pages[number - 1]["label"],
                "rect": list(rect) if rect else None,
            }
            search.close()
            textpage.close()
            page.close()
    block_pages = {}
    for block in blocks:
        needle = plain(block.get("text", ""))[:160]
        matches = [
            p["number"] for p in pages if len(needle) >= 12 and needle in p["_text"]
        ]
        if len(matches) == 1:
            block_pages[block["id"]] = matches[0]
        elif block["id"] in locations:
            block_pages[block["id"]] = locations[block["id"]]["page"]
    for page in pages:
        relevant = {
            b.get("section")
            for b in blocks
            if block_pages.get(b["id"]) == page["number"]
        }
        common = list((section_bounds or {}).values())
        bounds = (
            (section_bounds or {}).get(next(iter(relevant)))
            if len(relevant) == 1
            else None
        )
        if bounds is None and common and all(value == common[0] for value in common):
            bounds = common[0]
        outside = any(
            left < -2
            or right > page["width"] + 2
            or bottom < -2
            or top > page["height"] + 2
            for left, bottom, right, top in page["_rects"]
        )
        if bounds:
            left_limit, right_margin, top_margin, bottom_limit = bounds
            outside |= any(
                (left < left_limit - 4 or right > page["width"] - right_margin + 4)
                and bottom > bottom_limit + 4
                and top < page["height"] - top_margin - 4
                for left, bottom, right, top in page["_rects"]
            )
        if outside:
            warnings.append(
                {
                    "code": "print_area",
                    "page": page["number"],
                    "title": "Có nội dung vượt vùng in cần kiểm tra",
                    "description": "Phát hiện chữ/ảnh sát hoặc vượt giới hạn trang/vùng in nhận diện được. Không tự thu chữ hay xóa nội dung; hãy xem trang này bằng Word.",
                }
            )
        del page["_text"]
        del page["_rects"]
    return {
        "pages": pages,
        "page_count": len(pages),
        "headings": locations,
        "block_pages": block_pages,
        "warnings": warnings,
    }


def page_png(pdf_path, page_number, output_path, width=1000):
    with PDF_LOCK, closing(pdfium.PdfDocument(pdf_path)) as pdf:
        if page_number < 1 or page_number > len(pdf):
            raise PreviewError("Trang không tồn tại.")
        page = pdf[page_number - 1]
        scale = min(width / page.get_width(), 2.0)
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        bitmap.close()
        page.close()
    Path(output_path).write_bytes(buffer.getvalue())
    return Path(output_path)


def font_warnings(font):
    executable = shutil.which("fc-match")
    if executable:
        result = subprocess.run(
            [executable, "-f", "%{family}", font],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        actual = result.stdout.strip()
        if actual and font.casefold() not in actual.casefold():
            return [
                {
                    "code": "font_substitution",
                    "title": "Bản xem trước dùng phông thay thế",
                    "description": f"Phông yêu cầu: {font}; máy dựng dùng {actual}. Word có phông gốc có thể ngắt dòng/trang khác.",
                }
            ]
    return [
        {
            "code": "word_rendering",
            "title": "Cần xem lần cuối bằng Word",
            "description": "PDF được dựng bằng LibreOffice; vị trí ngắt trang có thể khác Microsoft Word hoặc máy thiếu phông.",
        }
    ]
