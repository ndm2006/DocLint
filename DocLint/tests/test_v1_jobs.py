import asyncio
from io import BytesIO
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from docx import Document
from fastapi.testclient import TestClient
from api import create_app
from core.xmlutils import NS
from v1.package import Package
from v1.renderer import PreviewError, find_office
from v1_fixtures import fixture


def unavailable(*args, **kwargs):
    raise PreviewError("Bộ dựng được tắt trong bài kiểm thử này.")


def wait_for(client, url, states=("review", "failed", "ready", "partial"), seconds=30):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        response = client.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        meta = response.json()
        if meta["status"] in states:
            return meta
        client.portal.call(asyncio.sleep, 0.03)
    raise AssertionError("Job did not complete within test deadline")


class JobAPIV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(self.tmp.name)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        self.data = fixture(1)

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.tmp.cleanup()

    def upload(self, data=None):
        r = self.client.post(
            "/api/v1/jobs",
            files={"file": ("báo cáo.docx", data if data is not None else self.data)},
        )
        self.assertEqual(r.status_code, 202, r.text)
        return r.json()

    @unittest.skipUnless(find_office(), "LibreOffice is required for integration test")
    def test_real_async_review_format_preview_download_report_delete(self):
        job = self.upload()
        url = job["urls"]["status"]
        self.assertEqual(self.client.get(url + "/download").status_code, 409)
        meta = wait_for(self.client, url)
        self.assertEqual(meta["status"], "review", meta.get("error"))
        self.assertTrue(meta["original_preview"]["available"])
        choices = {
            b["id"]: b["level"]
            for b in meta["analysis"]["blocks"]
            if b["role"] == "heading" and b.get("level") and not b.get("region")
        }
        r = self.client.post(
            url + "/format",
            json={
                "heading_levels": choices,
                "mode": "layout",
                "toc": "insert",
                "page_numbers": "arabic",
                "table_headers": ["t00001"],
            },
        )
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(self.client.post(url + "/format", json={}).status_code, 409)
        meta = wait_for(self.client, url, ("ready", "partial", "review"))
        self.assertEqual(meta["status"], "ready", meta.get("error"))
        self.assertTrue(meta["report"]["integrity"]["verified"])
        word = self.client.get(url + "/download")
        self.assertEqual(word.status_code, 200)
        Document(BytesIO(word.content))
        downloaded = Package(word.content)
        toc = downloaded.document.xpath(
            './/w:sdt[w:sdtPr/w:tag[@w:val="DocLintTOC"]]', namespaces=NS
        )[0]
        cached_numbers = [
            p.xpath("./w:r/w:t/text()", namespaces=NS)[-1]
            for p in toc.xpath("./w:sdtContent/w:p[w:r/w:tab]", namespaces=NS)
        ]
        locations = meta["report"]["layout"]["headings"]
        expected_numbers = [
            str(locations[b["id"]]["page"] - 1)
            for b in meta["analysis"]["blocks"]
            if b["id"] in locations
        ]
        self.assertTrue(cached_numbers)
        self.assertEqual(cached_numbers, expected_numbers)
        self.assertNotIn("0", cached_numbers)
        self.assertEqual(
            downloaded.xml("word/settings.xml").xpath(
                "./w:updateFields/@w:val", namespaces=NS
            ),
            ["false"],
        )
        self.assertEqual(
            toc.xpath('.//w:fldChar[@w:fldCharType="begin"]/@w:dirty', namespaces=NS),
            ["false"],
        )
        self.assertTrue(
            self.client.get(url + "/preview/original.pdf").content.startswith(b"%PDF")
        )
        self.assertTrue(
            self.client.get(url + "/preview/result.pdf").content.startswith(b"%PDF")
        )
        self.assertTrue(
            self.client.get(url + "/pages/result/1.png").content.startswith(b"\x89PNG")
        )
        self.assertEqual(
            self.client.get(url + "/pages/result/999.png").status_code, 404
        )
        self.assertEqual(self.client.get(url + "/pages/unknown/1.png").status_code, 404)
        self.assertTrue(
            self.client.get(url + "/report").json()["integrity"]["verified"]
        )
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse((self.app.state.jobs.store.root / job["id"]).exists())

    def test_missing_renderer_is_explicit_partial_and_reformat_keeps_deadline(self):
        with (
            patch("v1.jobs.render_pdf", side_effect=unavailable),
            patch("v1.pipeline.render_pdf", side_effect=unavailable),
        ):
            job = self.upload()
            url = job["urls"]["status"]
            meta = wait_for(self.client, url)
            expires = meta["expires_at"]
            self.assertFalse(meta["original_preview"]["available"])
            r = self.client.post(url + "/format", json={})
            self.assertEqual(r.status_code, 202)
            meta = wait_for(self.client, url, ("ready", "partial", "review"))
            self.assertEqual(meta["status"], "partial")
            first_hash = meta["report"]["integrity"]["source_sha256"]
            self.assertEqual(meta["expires_at"], expires)
            self.assertEqual(
                self.client.get(url + "/preview/result.pdf").status_code, 409
            )
            self.assertEqual(self.client.get(url + "/download").status_code, 200)
            self.client.post(url + "/format", json={"profile": "report"})
            second = wait_for(self.client, url, ("ready", "partial", "review"))
            self.assertEqual(second["report"]["integrity"]["source_sha256"], first_hash)
            self.assertEqual(second["expires_at"], expires)

    def test_invalid_file_options_and_paths(self):
        self.assertEqual(
            self.client.post(
                "/api/v1/jobs", files={"file": ("x.pdf", b"fake")}
            ).status_code,
            415,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/jobs", files={"file": ("x.docx", b"")}
            ).status_code,
            422,
        )
        job = self.upload(b"fake")
        meta = wait_for(self.client, job["urls"]["status"])
        self.assertEqual(meta["status"], "failed")
        self.assertEqual(self.client.get(job["urls"]["download"]).status_code, 409)
        self.assertEqual(self.client.get("/api/v1/jobs/not-a-uuid").status_code, 404)
        with patch("v1.jobs.render_pdf", side_effect=unavailable):
            job = self.upload()
            url = job["urls"]["status"]
            wait_for(self.client, url)
            for payload in [
                {"mode": "invalid"},
                {"unknown": True},
                {"locked_blocks": ["missing"]},
                {"toc": "replace"},
                {"heading_levels": {"p00001": 9}},
            ]:
                self.assertEqual(
                    self.client.post(url + "/format", json=payload).status_code,
                    422,
                    payload,
                )
            self.assertEqual(self.client.get(url).json()["status"], "review")

    def test_cancel_active_renderer_deletes_only_after_stopping(self):
        def slow(data, destination, cancel=None, **kwargs):
            while not cancel.is_set():
                time.sleep(0.01)
            raise PreviewError("Đã hủy")

        with patch("v1.jobs.render_pdf", side_effect=slow):
            job = self.upload()
            url = job["urls"]["status"]
            wait_for(self.client, url, ("analyzing",))
            response = self.client.delete(url)
            self.assertEqual(response.status_code, 204)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertFalse((self.app.state.jobs.store.root / job["id"]).exists())

    def test_bounded_queue_rejects_without_leaving_an_extra_original(self):
        def slow(data, destination, cancel=None, **kwargs):
            while not cancel.is_set():
                time.sleep(0.01)
            raise PreviewError("Đã hủy")

        with patch("v1.jobs.render_pdf", side_effect=slow):
            active = self.upload()
            wait_for(self.client, active["urls"]["status"], ("analyzing",))
            queued = [self.upload() for _ in range(4)]
            extra = self.client.post(
                "/api/v1/jobs", files={"file": ("x.docx", self.data)}
            )
            self.assertEqual(extra.status_code, 429)
            self.assertEqual(
                len(list(self.app.state.jobs.store.root.glob("*/original.docx"))), 5
            )
            for job in [active, *queued]:
                self.client.delete(job["urls"]["status"])

    def test_expiry_from_intake_and_physical_cleanup(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            TestClient(create_app(tmp, ttl=0.4)) as client,
            patch("v1.jobs.render_pdf", side_effect=unavailable),
        ):
            r = client.post("/api/v1/jobs", files={"file": ("x.docx", self.data)})
            self.assertEqual(r.status_code, 202)
            job = r.json()
            wait_for(client, job["urls"]["status"])
            client.portal.call(asyncio.sleep, 0.5)
            self.assertEqual(client.get(job["urls"]["status"]).status_code, 404)
            self.assertFalse((Path(tmp) / "v1-jobs" / job["id"]).exists())

    def test_recover_interrupted_jobs_and_delete_expired(self):
        store = self.app.state.jobs.store
        job = store.create(self.data, "x.docx")
        store.update(job["id"], status="formatting", analysis={"blocks": []})
        store.recover()
        self.assertEqual(store.read(job["id"])["status"], "review")
        store.update(job["id"], expires=0)
        store.recover()
        self.assertFalse(store.folder(job["id"]).exists())

    def test_rate_limit_and_capabilities(self):
        manager = self.app.state.jobs
        self.assertTrue(all(manager.rate_allowed("a") for _ in range(10)))
        self.assertFalse(manager.rate_allowed("a"))
        cap = self.client.get("/api/v1/capabilities").json()
        self.assertFalse(cap["ai_api"])
        self.assertEqual(cap["workers"], 1)
        self.assertEqual(cap["ttl_seconds"], 1800)

    def test_two_concurrent_format_requests_are_not_both_accepted(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from v1.routes import Editor as OriginalEditor

        entered, release = threading.Event(), threading.Event()

        def validate(data, options):
            entered.set()
            if not release.wait(3):
                raise AssertionError("Test did not release validator")
            return OriginalEditor(data, options)

        with (
            patch("v1.jobs.render_pdf", side_effect=unavailable),
            patch("v1.pipeline.render_pdf", side_effect=unavailable),
        ):
            job = self.upload()
            url = job["urls"]["status"]
            wait_for(self.client, url)
            with (
                patch("v1.routes.Editor", side_effect=validate),
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                first = pool.submit(self.client.post, url + "/format", json={})
                self.assertTrue(entered.wait(2))
                second = pool.submit(self.client.post, url + "/format", json={})
                time.sleep(0.05)
                release.set()
                statuses = sorted(
                    [
                        first.result(timeout=5).status_code,
                        second.result(timeout=5).status_code,
                    ]
                )
            self.assertEqual(statuses, [202, 409])
            meta = wait_for(self.client, url, ("ready", "partial", "review"))
            self.assertEqual(meta["revision"], 1)

    def test_format_limit_does_not_extend_session(self):
        with patch("v1.jobs.render_pdf", side_effect=unavailable):
            job = self.upload()
            url = job["urls"]["status"]
            meta = wait_for(self.client, url)
            self.app.state.jobs.store.update(job["id"], revision=10)
            response = self.client.post(url + "/format", json={})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(
                self.client.get(url).json()["expires_at"], meta["expires_at"]
            )
