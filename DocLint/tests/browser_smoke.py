"""Run against a running dev server; no uploaded document is committed to Git."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright, expect

BASE = Path(__file__).resolve().parents[1]
URL = os.environ.get('DOCLINT_TEST_URL', 'http://127.0.0.1:8000')
SOURCE = Path(os.environ.get('DOCLINT_TEST_DOCX', BASE / 'test_input.docx'))
SCREENSHOTS = os.environ.get('DOCLINT_SCREENSHOT_DIR')


def screenshot(page, name):
    if SCREENSHOTS:
        folder = Path(SCREENSHOTS)
        folder.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(folder / name), full_page=True)


def main():
    with sync_playwright() as p, TemporaryDirectory() as downloads:
        browser_path = os.environ.get('DOCLINT_BROWSER_PATH')
        options = {'executable_path': browser_path} if browser_path else {}
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'], **options)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(URL)
            expect(page.locator('#profile-select option')).to_have_count(2)
            screenshot(page, 'desktop.png')
            expect(page.locator('#submit-button')).to_be_disabled()
            page.locator('#file-input').set_input_files({'name': 'invalid.pdf', 'mimeType': 'application/pdf', 'buffer': b'fake'})
            expect(page.locator('#error-box')).to_be_visible()
            page.locator('#file-input').set_input_files(str(SOURCE))
            expect(page.locator('#submit-button')).to_be_enabled()
            page.locator('#submit-button').click()
            expect(page.locator('#results')).to_be_visible()
            screenshot(page, 'desktop-results.png')
            with page.expect_download() as pending:
                page.locator('#download-button').click()
            download = pending.value
            assert download.suggested_filename.endswith('_doclint.docx')
            download.save_as(str(Path(downloads) / 'result.docx'))
            from docx import Document
            Document(Path(downloads) / 'result.docx')
            page.locator('#delete-session').click()
            expect(page.locator('#expiry-label')).to_contain_text('Đã xóa')
            expect(page.locator('#download-button')).to_be_disabled()
            page.set_viewport_size({'width': 390, 'height': 844})
            page.goto(URL)
            expect(page.locator('#profile-select option')).to_have_count(2)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            screenshot(page, 'mobile.png')
            page.select_option('#profile-select', 'report')
            page.locator('#file-input').set_input_files(str(SOURCE))
            page.locator('#submit-button').click()
            expect(page.locator('#results')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            screenshot(page, 'mobile-results.png')
            page.locator('#delete-session').click()
            expect(page.locator('#expiry-label')).to_contain_text('Đã xóa')
            assert not errors, errors
            print('PASS: desktop/mobile, both presets, validation, upload, report, download, delete; no overflow or JS errors.')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
