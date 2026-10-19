import asyncio
import time
from urllib.parse import quote
from fastapi import File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from core.processor import DocumentError, MAX_UPLOAD
from v1.editor import Editor
from v1.options import FormatOptions
from v1.renderer import capabilities, page_png, PreviewError

MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def attach_routes(app, manager):
    store = manager.store
    validation_gate = asyncio.Semaphore(1)

    def require(job_id):
        meta = store.read(job_id)
        if meta is None:
            raise HTTPException(404, "Phiên đã hết hạn, đã xóa hoặc không tồn tại.")
        return meta

    def artifact(job_id, name, mime, filename=None):
        require(job_id)
        try:
            data = (store.folder(job_id) / name).read_bytes()
        except FileNotFoundError:
            raise HTTPException(404, "Tệp chưa sẵn sàng hoặc đã hết hạn.") from None
        headers = (
            {
                "Content-Disposition": "attachment; filename*=utf-8''"
                + quote(filename, safe="")
            }
            if filename
            else {}
        )
        return Response(data, media_type=mime, headers=headers)

    @app.get("/api/v1/capabilities")
    async def get_capabilities():
        return {
            "version": "1.0",
            **capabilities(),
            "max_upload_mb": 15,
            "queue_capacity": manager.queue.maxsize,
            "workers": 1,
            "ttl_seconds": store.ttl,
            "ai_api": False,
        }

    @app.post("/api/v1/jobs", status_code=202)
    async def upload_job(request: Request, file: UploadFile = File(...)):
        try:
            if manager.queue.full():
                raise HTTPException(
                    429,
                    "Hàng đợi đang đầy. Vui lòng thử lại sau.",
                    headers={"Retry-After": "15"},
                )
            client = request.client.host if request.client else "unknown"
            if not manager.rate_allowed(client):
                raise HTTPException(
                    429,
                    "Tối đa 10 lượt tải lên mỗi phút. Hãy chờ rồi thử lại.",
                    headers={"Retry-After": "60"},
                )
            filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
            if not filename.lower().endswith(".docx"):
                raise HTTPException(415, "Chỉ hỗ trợ tệp .docx.")
            data = bytearray()
            while chunk := await file.read(64 * 1024):
                data.extend(chunk)
                if len(data) > MAX_UPLOAD:
                    raise HTTPException(413, "Tệp vượt giới hạn 15 MB.")
            if not data:
                raise HTTPException(422, "Tệp không có dữ liệu.")
            received_at = request.scope.get("doclint_received_at", time.time())
            if received_at + store.ttl <= time.time():
                raise HTTPException(408, "Thời gian tải lên vượt thời hạn phiên.")
            meta = await run_in_threadpool(
                store.create, bytes(data), filename, received_at
            )
            if not manager.submit(meta["id"], "analyze"):
                store.delete(meta["id"])
                raise HTTPException(
                    429,
                    "Hàng đợi vừa đầy. Vui lòng thử lại sau.",
                    headers={"Retry-After": "15"},
                )
            manager.schedule_expiry(meta)
            return store.public(meta)
        finally:
            await file.close()

    @app.get("/api/v1/jobs/{job_id}")
    async def job_status(job_id: str):
        meta = require(job_id)
        result = store.public(meta)
        result["queue_waiting"] = manager.queue.qsize()
        return result

    @app.post("/api/v1/jobs/{job_id}/format", status_code=202)
    async def format_job(job_id: str, options: FormatOptions):
        meta = require(job_id)
        if meta["status"] not in {"review", "ready", "partial"} or not meta.get(
            "analysis"
        ):
            raise HTTPException(409, "Công việc đang chạy hoặc chưa phân tích xong.")
        if manager.queue.full():
            raise HTTPException(
                429,
                "Hàng đợi đang đầy. Vui lòng thử lại sau.",
                headers={"Retry-After": "15"},
            )
        async with validation_gate:
            current = require(job_id)
            if current.get("revision", 0) != meta.get("revision", 0) or current[
                "status"
            ] not in {"review", "ready", "partial"}:
                raise HTTPException(
                    409, "Một yêu cầu khác vừa được tiếp nhận; hãy chờ kết quả."
                )
            try:
                data = await run_in_threadpool(
                    (store.folder(job_id) / "original.docx").read_bytes
                )
                await run_in_threadpool(Editor, data, options)
            except FileNotFoundError:
                raise HTTPException(404, "Phiên đã hết hạn.") from None
            except DocumentError as exc:
                raise HTTPException(422, str(exc)) from exc
            latest = store.read(job_id)
            if not latest:
                raise HTTPException(404, "Phiên đã hết hạn.")
            if latest.get("revision", 0) != meta.get("revision", 0) or latest[
                "status"
            ] not in {"review", "ready", "partial"}:
                raise HTTPException(
                    409,
                    "Một yêu cầu dàn trang khác vừa được tiếp nhận. Hãy chờ kết quả.",
                )
            if latest.get("revision", 0) >= 10:
                raise HTTPException(
                    429,
                    "Tối đa 10 lần dàn trang trong một phiên. Hãy tải lại tệp nếu cần tiếp tục.",
                )
            revision = latest.get("revision", 0) + 1
            meta = store.update(
                job_id,
                status="queued",
                stage="Đang chờ dàn trang",
                report=None,
                revision=revision,
                options=options.model_dump(),
                error=None,
            )
            if not manager.submit(job_id, "format", options.model_dump()):
                store.update(job_id, status="review")
                raise HTTPException(429, "Hàng đợi đang đầy.")
            return store.public(meta)

    @app.get("/api/v1/jobs/{job_id}/download")
    async def download_result(job_id: str):
        meta = require(job_id)
        if meta["status"] not in {"ready", "partial"} or not meta.get("report", {}).get(
            "integrity", {}
        ).get("verified"):
            raise HTTPException(409, "Chưa có kết quả đã đối chiếu toàn vẹn.")
        filename = meta["filename"][:-5][:140] + "_doclint.docx"
        return artifact(job_id, "result.docx", MIME, filename)

    @app.get("/api/v1/jobs/{job_id}/report")
    async def download_report(job_id: str):
        meta = require(job_id)
        if meta["status"] not in {"ready", "partial"} or not meta.get("report"):
            raise HTTPException(409, "Báo cáo chưa sẵn sàng.")
        import json

        return Response(
            json.dumps(meta["report"], ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="doclint-report.json"'
            },
        )

    @app.get("/api/v1/jobs/{job_id}/preview/{variant}.pdf")
    async def preview_pdf(job_id: str, variant: str):
        meta = require(job_id)
        if variant not in {"original", "result"}:
            raise HTTPException(404, "Bản xem trước không tồn tại.")
        available = (
            meta["original_preview"]["available"]
            if variant == "original"
            else bool(
                meta.get("report")
                and meta["report"].get("preview", {}).get("available")
                and meta["status"] in {"ready", "partial"}
            )
        )
        if not available:
            raise HTTPException(409, "Bản PDF chưa sẵn sàng.")
        return artifact(
            job_id, f"{variant}.pdf", "application/pdf", f"doclint-{variant}.pdf"
        )

    @app.get("/api/v1/jobs/{job_id}/pages/{variant}/{page_number}.png")
    async def preview_page(job_id: str, variant: str, page_number: int):
        meta = require(job_id)
        if variant not in {"original", "result"} or not 1 <= page_number <= 120:
            raise HTTPException(404, "Trang không tồn tại.")
        preview = (
            meta["original_preview"]
            if variant == "original"
            else (meta.get("report") or {}).get("preview", {})
        )
        if variant == "result" and meta["status"] not in {"ready", "partial"}:
            raise HTTPException(409, "Kết quả đang được tạo lại.")
        if not preview.get("available"):
            raise HTTPException(409, preview.get("reason", "Chưa có bản xem trước."))
        if page_number > preview.get("page_count", 0):
            raise HTTPException(404, "Trang không tồn tại.")
        folder = store.folder(job_id)
        cached = folder / "pages" / variant / f"{page_number}.png"
        if not cached.is_file():
            cached.parent.mkdir(parents=True, exist_ok=True)
            try:
                await run_in_threadpool(
                    page_png, folder / f"{variant}.pdf", page_number, cached
                )
            except (PreviewError, FileNotFoundError):
                raise HTTPException(
                    404, "Không dựng được trang hoặc phiên đã hết hạn."
                ) from None
        require(job_id)
        try:
            return Response(cached.read_bytes(), media_type="image/png")
        except FileNotFoundError:
            raise HTTPException(404, "Phiên đã hết hạn.") from None

    @app.delete("/api/v1/jobs/{job_id}")
    async def delete_job(job_id: str):
        # Idempotent deletion; active renderers are stopped before claiming success.
        deleted = await manager.delete(job_id)
        return (
            Response(status_code=204)
            if deleted
            else JSONResponse({"status": "deleting"}, status_code=202)
        )
