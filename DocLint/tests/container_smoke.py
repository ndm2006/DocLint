"""Standard-library HTTP smoke check; can run in the runtime image offline."""

from io import BytesIO
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
import zipfile

ADDRESS = "http://127.0.0.1:18090"


def request(path, method="GET", data=None, content_type=None):
    headers = {"Content-Type": content_type} if content_type else {}
    with urlopen(
        Request(ADDRESS + path, data=data, headers=headers, method=method), timeout=10
    ) as response:
        return response.status, response.read()


def wait(url, states):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        _, raw = request(url)
        meta = json.loads(raw)
        if meta["status"] in states:
            return meta
        if meta["status"] == "failed":
            raise AssertionError(meta.get("error"))
        time.sleep(0.1)
    raise AssertionError("Job timed out")


def main():
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api:app",
            "--host",
            "127.0.0.1",
            "--port",
            "18090",
            "--no-access-log",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                request("/api/v1/health")
                break
            except URLError:
                if process.poll() is not None:
                    raise AssertionError("Server failed to start")
                time.sleep(0.1)
        _, raw = request("/api/v1/capabilities")
        assert json.loads(raw)["renderer"]
        source = Path("static/demo.docx").read_bytes()
        boundary = "DocLintContainerSmokeBoundary"
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="demo.docx"\r\nContent-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n'.encode()
            + source
            + f"\r\n--{boundary}--\r\n".encode()
        )
        status, raw = request(
            "/api/v1/jobs", "POST", body, f"multipart/form-data; boundary={boundary}"
        )
        assert status == 202
        job = json.loads(raw)
        url = job["urls"]["status"]
        meta = wait(url, {"review"})
        assert meta["original_preview"]["available"], meta["original_preview"]
        analysis = meta["analysis"]
        options = {
            "mode": "layout",
            "cover": "academic" if analysis["cover_end"] else "keep",
            "cover_end": analysis["cover_end"],
            "heading_levels": {
                b["id"]: b["level"]
                for b in analysis["blocks"]
                if b["role"] == "heading" and b.get("level") and not b.get("region")
            },
            "toc": "replace" if analysis["toc_region"] else "insert",
            "page_numbers": "arabic",
            "table_headers": [
                b["id"]
                for b in analysis["blocks"]
                if b["type"] == "table" and b["simple"]
            ],
        }
        request(
            url + "/format", "POST", json.dumps(options).encode(), "application/json"
        )
        result = wait(url, {"ready", "partial", "review"})
        assert result["status"] == "ready", result.get("error") or result.get("report")
        report = result["report"]
        assert report["integrity"]["verified"]
        assert report["toc_status"] == "verified"
        assert (
            report["integrity"]["source_sha256"] == hashlib.sha256(source).hexdigest()
        )
        status, word = request(url + "/download")
        assert status == 200
        with zipfile.ZipFile(BytesIO(word)) as archive:
            assert archive.testzip() is None
        status, pdf = request(url + "/preview/result.pdf")
        assert status == 200 and pdf.startswith(b"%PDF")
        status, png = request(url + "/pages/result/1.png")
        assert status == 200 and png.startswith(b"\x89PNG")
        status, _ = request(url, "DELETE")
        assert status == 204
        print(
            "PASS: offline runtime, non-root/read-only filesystem, upload/review/format, verified TOC, DOCX/PDF/PNG download, delete."
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    main()
