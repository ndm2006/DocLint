"""Exercise the V1 review/preview/download workflow against a running server."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from docx import Document
from playwright.sync_api import sync_playwright, expect

BASE = Path(__file__).resolve().parents[1]
URL = os.environ.get("DOCLINT_TEST_URL", "http://127.0.0.1:8000").rstrip("/")
SOURCE = Path(os.environ.get("DOCLINT_TEST_DOCX", BASE / "static" / "demo.docx"))
SCREENSHOTS = os.environ.get("DOCLINT_SCREENSHOT_DIR")


def screenshot(page, name):
    if SCREENSHOTS:
        folder = Path(SCREENSHOTS)
        folder.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(folder / name), full_page=True)


def main():
    original = SOURCE.read_bytes()
    with sync_playwright() as p, TemporaryDirectory() as downloads:
        path = os.environ.get("DOCLINT_BROWSER_PATH")
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"],
            **({"executable_path": path} if path else {}),
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(120000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.goto(URL)
            expect(page.locator("#profile-select option")).to_have_count(2)
            capabilities = page.request.get(URL + "/api/v1/capabilities").json()
            assert capabilities["renderer"], (
                "Install LibreOffice before the full browser readiness check."
            )
            screenshot(page, "desktop.png")
            expect(page.locator("#submit-button")).to_be_disabled()
            page.locator("#file-input").set_input_files(
                {
                    "name": "invalid.pdf",
                    "mimeType": "application/pdf",
                    "buffer": b"fake",
                }
            )
            expect(page.locator("#error-box")).to_be_visible()
            page.locator("#file-input").set_input_files(str(SOURCE))
            with page.expect_response(
                lambda r: r.url.endswith("/api/v1/jobs") and r.request.method == "POST"
            ) as created:
                page.locator("#submit-button").click()
            job = created.value.json()
            expect(page.locator("#review")).to_be_visible()
            meta = page.request.get(URL + job["urls"]["status"]).json()
            assert meta["original_preview"]["available"], meta["original_preview"]
            page.locator("#approve-headings").click()
            page.select_option("#mode-select", "layout")
            if meta["analysis"]["cover_end"]:
                page.select_option("#cover-select", "academic")
            if any(b["role"] == "heading" for b in meta["analysis"]["blocks"]):
                page.select_option(
                    "#toc-select",
                    "replace" if meta["analysis"]["toc_region"] else "insert",
                )
            page.locator("#page-numbers").check()
            table_section = page.locator("details").filter(
                has=page.locator("#table-review")
            )
            table_section.locator("summary").click()
            for checkbox in page.locator("#table-review input:not(:disabled)").all():
                checkbox.check()
            screenshot(page, "review.png")
            page.locator("#format-button").click()
            expect(page.locator("#results")).to_be_visible()
            meta = page.request.get(URL + job["urls"]["status"]).json()
            assert meta["report"]["integrity"]["verified"]
            assert meta["report"]["preview"]["available"], meta.get("error")
            expect(page.locator("#result-image")).to_be_visible()
            screenshot(page, "desktop-results.png")
            with page.expect_download() as pending:
                page.locator("#download-button").click()
            download = pending.value
            assert download.suggested_filename.endswith("_doclint.docx")
            output = Path(downloads) / "result.docx"
            download.save_as(str(output))
            Document(output)
            with page.expect_download() as pending:
                page.locator("#report-button").click()
            pending.value.save_as(str(Path(downloads) / "report.json"))
            page.reload()
            expect(page.locator("#results")).to_be_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            screenshot(page, "mobile-results.png")
            page.locator("#revise-button").click()
            expect(page.locator("#review")).to_be_visible()
            page.select_option("#profile-select", "report")
            page.locator("#format-button").click()
            expect(page.locator("#results")).to_be_visible()
            second = page.request.get(URL + job["urls"]["status"]).json()
            assert (
                second["report"]["integrity"]["source_sha256"]
                == meta["report"]["integrity"]["source_sha256"]
            )
            assert second["expires_at"] == meta["expires_at"]
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#delete-session").click()
            expect(page.locator("#upload-workspace")).to_be_visible()
            assert page.request.get(URL + job["urls"]["status"]).status == 404
            assert not errors, errors
            assert SOURCE.read_bytes() == original
            print(
                "PASS: desktop/mobile, review, both templates, real previews, DOCX/report download, reload, reformat from original, delete; no JS errors."
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
