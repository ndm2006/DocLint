"""Bounded single-renderer queue and private jobs expiring from intake time."""

import asyncio
from collections import defaultdict, deque
from contextlib import suppress
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import threading
import time
from uuid import UUID, uuid4
from core.processor import DocumentError
from v1.analysis import Analysis
from v1.package import Package
from v1.pipeline import format_document
from v1.renderer import PreviewError, render_pdf, inspect_pdf


class JobStore:
    def __init__(self, root, ttl=1800):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.ttl = ttl
        self.lock = threading.RLock()

    def folder(self, job_id):
        if str(UUID(job_id)) != job_id:
            raise ValueError("Invalid job")
        return self.root / job_id

    def read(self, job_id, expired=False):
        try:
            with self.lock:
                meta = json.loads(
                    (self.folder(job_id) / "job.json").read_text(encoding="utf-8")
                )
                if not expired and (
                    meta["expires"] <= time.time() or meta.get("status") == "deleting"
                ):
                    return None
                return meta
        except (ValueError, KeyError, FileNotFoundError):
            return None

    def update(self, job_id, **values):
        with self.lock:
            folder = self.folder(job_id)
            meta = self.read(job_id, expired=True)
            if meta is None or not folder.is_dir():
                return None
            meta.update(values)
            self._save(folder, meta)
            return meta

    def _save(self, folder, meta):
        temporary = folder / "job.pending.json"
        temporary.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        temporary.replace(folder / "job.json")

    def create(self, data, filename, received_at=None):
        now = received_at or time.time()
        job_id = str(uuid4())
        folder = self.folder(job_id)
        folder.mkdir(mode=0o700)
        meta = {
            "id": job_id,
            "filename": filename,
            "status": "queued",
            "stage": "Đang chờ phân tích",
            "created_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "expires": now + self.ttl,
            "expires_at": datetime.fromtimestamp(
                now + self.ttl, timezone.utc
            ).isoformat(),
            "revision": 0,
            "analysis": None,
            "original_preview": {"available": False, "reason": "Chưa dựng"},
            "report": None,
        }
        try:
            (folder / "original.docx").write_bytes(data)
            self._save(folder, meta)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return meta

    def delete(self, job_id):
        with self.lock:
            try:
                shutil.rmtree(self.folder(job_id), ignore_errors=True)
            except ValueError:
                pass

    def recover(self):
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue
            try:
                self.folder(folder.name)
            except ValueError:
                continue
            meta = self.read(folder.name, expired=True)
            if meta is None:
                if folder.stat().st_mtime + self.ttl <= time.time():
                    self.delete(folder.name)
            elif meta["expires"] <= time.time() or meta["status"] == "deleting":
                self.delete(folder.name)
            elif meta["status"] in {"queued", "analyzing", "formatting"}:
                self.update(
                    folder.name,
                    status="review" if meta.get("analysis") else "failed",
                    stage="Máy chủ vừa khởi động lại; hãy chọn xử lý lại.",
                    error="Công việc trước đã bị gián đoạn.",
                )

    def public(self, meta):
        result = {key: value for key, value in meta.items() if key != "expires"}
        job_id = meta["id"]
        result["urls"] = {
            "status": f"/api/v1/jobs/{job_id}",
            "delete": f"/api/v1/jobs/{job_id}",
            "download": f"/api/v1/jobs/{job_id}/download",
            "report": f"/api/v1/jobs/{job_id}/report",
            "original_pdf": f"/api/v1/jobs/{job_id}/preview/original.pdf",
            "result_pdf": f"/api/v1/jobs/{job_id}/preview/result.pdf",
        }
        return result


class JobManager:
    def __init__(self, store, capacity=4):
        self.store = store
        self.queue = asyncio.Queue(maxsize=capacity)
        self.cancellations = {}
        self.active = None
        self.running_done = {}
        self.deadlines = set()
        self.task = None
        self.sweeper = None
        self.rates = defaultdict(deque)

    def rate_allowed(self, client):
        now = time.monotonic()
        if len(self.rates) > 1000:
            self.rates = defaultdict(
                deque, {k: v for k, v in self.rates.items() if v and v[-1] > now - 60}
            )
        entries = self.rates[client]
        while entries and entries[0] <= now - 60:
            entries.popleft()
        if len(entries) >= 10:
            return False
        entries.append(now)
        return True

    async def start(self):
        self.store.recover()
        self.task = asyncio.create_task(self.worker())
        self.sweeper = asyncio.create_task(self.sweep())
        for folder in self.store.root.iterdir():
            if folder.is_dir():
                meta = self.store.read(folder.name)
                if meta:
                    self.schedule_expiry(meta)

    async def stop(self):
        for event in self.cancellations.values():
            event.set()
        for task in [self.sweeper, *self.deadlines]:
            if task:
                task.cancel()
        await asyncio.gather(
            *(t for t in [self.sweeper, *self.deadlines] if t), return_exceptions=True
        )
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    def schedule_expiry(self, meta):
        async def expiry():
            await asyncio.sleep(max(0, meta["expires"] - time.time()))
            await self.delete(meta["id"])

        task = asyncio.create_task(expiry())
        self.deadlines.add(task)
        task.add_done_callback(self.deadlines.discard)

    async def sweep(self):
        while True:
            await asyncio.sleep(10)
            for folder in list(self.store.root.iterdir()):
                if folder.is_dir():
                    meta = self.store.read(folder.name, expired=True)
                    if meta and meta["expires"] <= time.time():
                        await self.delete(folder.name)

    def submit(self, job_id, action, options=None):
        if self.queue.full():
            return False
        self.queue.put_nowait((job_id, action, options))
        return True

    async def delete(self, job_id):
        event = self.cancellations.get(job_id)
        if event:
            event.set()
        if self.active == job_id:
            self.store.update(
                job_id, status="deleting", stage="Đang dừng bộ xử lý và xóa tệp"
            )
            done = self.running_done.get(job_id)
            if done:
                try:
                    await asyncio.wait_for(done.wait(), timeout=2)
                except asyncio.TimeoutError:
                    return False
        self.store.delete(job_id)
        return True

    async def worker(self):
        while True:
            job_id, action, options = await self.queue.get()
            meta = self.store.read(job_id)
            if not meta:
                self.store.delete(job_id)
                self.queue.task_done()
                continue
            event = threading.Event()
            done = asyncio.Event()
            self.cancellations[job_id] = event
            self.running_done[job_id] = done
            self.active = job_id
            execution = asyncio.create_task(
                asyncio.to_thread(self.execute, job_id, action, options, event)
            )
            try:
                await asyncio.shield(execution)
            except asyncio.CancelledError:
                event.set()
                with suppress(Exception):
                    await execution
                raise
            finally:
                latest = self.store.read(job_id, expired=True)
                if (
                    event.is_set()
                    or latest is None
                    or latest["expires"] <= time.time()
                    or latest["status"] == "deleting"
                ):
                    self.store.delete(job_id)
                self.cancellations.pop(job_id, None)
                self.running_done.pop(job_id, None)
                self.active = None
                done.set()
                self.queue.task_done()

    def execute(self, job_id, action, options, cancel):
        folder = self.store.folder(job_id)
        try:
            if cancel.is_set():
                return
            data = (folder / "original.docx").read_bytes()
            if action == "analyze":
                self.store.update(
                    job_id, status="analyzing", stage="Đang nhận diện cấu trúc tài liệu"
                )
                analysis = Analysis(Package(data)).public()
                self.store.update(
                    job_id, analysis=analysis, stage="Đang dựng bản gốc để đối chiếu"
                )
                try:
                    render_pdf(data, folder / "original.pdf", cancel=cancel)
                    inspection = inspect_pdf(folder / "original.pdf")
                    preview = {
                        "available": True,
                        "page_count": inspection["page_count"],
                        "pages": inspection["pages"],
                    }
                except PreviewError as exc:
                    preview = {"available": False, "reason": str(exc)}
                if not cancel.is_set():
                    self.store.update(
                        job_id,
                        status="review",
                        stage="Hãy duyệt cấu trúc và chọn phạm vi sửa",
                        original_preview=preview,
                        error=None,
                    )
            else:
                self.store.update(job_id, status="formatting", stage="Đang chuẩn hóa")
                for name in ("result.docx", "result.pdf"):
                    (folder / name).unlink(missing_ok=True)
                shutil.rmtree(folder / "pages" / "result", ignore_errors=True)
                output, report = format_document(
                    data,
                    options,
                    folder,
                    cancel,
                    lambda stage: self.store.update(job_id, stage=stage),
                )
                if not cancel.is_set():
                    self.store.update(
                        job_id,
                        status=report["status"],
                        stage="Đã đối chiếu và xuất bản riêng",
                        report=report,
                        error=None,
                    )
        except DocumentError as exc:
            if not cancel.is_set():
                self.store.update(
                    job_id,
                    status="review" if action == "format" else "failed",
                    error=str(exc),
                    stage="Chưa thể hoàn tất; hãy xem thông báo",
                )
        except Exception:
            if not cancel.is_set():
                # No document text, filenames, paths, or raw renderer output in logs/API.
                self.store.update(
                    job_id,
                    status="review" if action == "format" else "failed",
                    error="Không xử lý được tài liệu này. Bản gốc vẫn được giữ để bạn thử lại.",
                    stage="Công việc chưa hoàn tất",
                )
