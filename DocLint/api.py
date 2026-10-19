"""Run with: python -m uvicorn api:app --host 0.0.0.0 --port 8000"""
import asyncio
from contextlib import asynccontextmanager, suppress
import logging
import os
from pathlib import Path
import tempfile
import time
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from core.processor import DocumentError, MAX_UPLOAD, process_document
from core.profiles import DESCRIPTIONS, PROFILES
from core.sessions import SessionStore

BASE = Path(__file__).resolve().parent
MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
logger = logging.getLogger('doclint')

class LimitUploadBody:
    """Bound the entire request, including chunked multipart bodies, before parsing."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'POST':
            return await self.app(scope, receive, send)
        limit = MAX_UPLOAD + 1024 * 1024  # multipart fields and headers
        headers = dict(scope.get('headers', []))
        async def too_large():
            await JSONResponse({'detail': 'Dung lượng tải lên vượt giới hạn 15 MB.'}, status_code=413)(scope, receive, send)
        try:
            if int(headers.get(b'content-length', b'0')) > limit:
                return await too_large()
        except ValueError:
            return await JSONResponse({'detail': 'Content-Length không hợp lệ.'}, status_code=400)(scope, receive, send)
        messages, consumed = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            consumed += len(message.get('body', b''))
            if consumed > limit:
                return await too_large()
            messages.append(message)
            if not message.get('more_body', False):
                break
        iterator = iter(messages)
        async def replay():
            message = next(iterator, None)
            return message if message is not None else await receive()
        await self.app(scope, replay, send)


def create_app(storage_path=None, ttl=1800):
    store = SessionStore(storage_path or os.environ.get('DOCLINT_STORAGE', str(Path(tempfile.gettempdir()) / 'doclint-sessions')), ttl)
    gate = asyncio.Semaphore(2)

    @asynccontextmanager
    async def lifespan(app):
        store.cleanup()
        async def sweep():
            while True:
                await asyncio.sleep(10)
                await run_in_threadpool(store.cleanup)
        task = asyncio.create_task(sweep())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            pending = list(app.state.expiry_tasks)
            for expiry_task in pending:
                expiry_task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    app = FastAPI(title='DocLint', version='0.2.0', lifespan=lifespan)
    app.state.store = store
    app.add_middleware(LimitUploadBody)

    @app.middleware('http')
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.update({
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        })
        return response

    @app.get('/api/v1/health')
    def health():
        return {'status': 'ok'}

    @app.get('/api/v1/profiles')
    def profiles():
        return [{'id': key, **value} for key, value in DESCRIPTIONS.items()]

    @app.post('/api/v1/lint', status_code=201)
    async def lint(file: UploadFile = File(...), profile: str = Form('hust')):
        try:
            if profile not in PROFILES:
                raise HTTPException(422, 'Mẫu định dạng không được hỗ trợ.')
            filename = (file.filename or '').replace('\\', '/').rsplit('/', 1)[-1]
            if not filename.lower().endswith('.docx'):
                raise HTTPException(415, 'Chỉ hỗ trợ tệp .docx. Hãy lưu tệp .doc hoặc .docm sang DOCX trước.')
            data = bytearray()
            while chunk := await file.read(64 * 1024):
                data.extend(chunk)
                if len(data) > MAX_UPLOAD:
                    raise HTTPException(413, 'Tệp vượt giới hạn 15 MB.')
            async with gate:
                try:
                    processed = await run_in_threadpool(process_document, bytes(data), profile)
                except DocumentError as e:
                    raise HTTPException(422, str(e)) from e
                except Exception:
                    logger.error('DOCX processing failed; no document contents logged.')
                    raise HTTPException(500, 'Chưa xử lý được tài liệu này. Tệp gốc của bạn vẫn nguyên vẹn.') from None
                download_name = filename[:-5][:140] + '_doclint.docx'
                record = await run_in_threadpool(store.create, processed.data, download_name, processed.report)
            # A per-session deadline plus periodic/startup sweeps covers abandoned jobs.
            deadline = record['expires']
            async def expire():
                await asyncio.sleep(max(0, deadline - time.time()))
                await run_in_threadpool(store.delete, record['session_id'])
            task = asyncio.create_task(expire())
            # Keep references until completion (event loop uses weak references).
            app.state.expiry_tasks.add(task)
            task.add_done_callback(app.state.expiry_tasks.discard)
            record.pop('expires')
            return {**record, 'download_url': f"/api/v1/sessions/{record['session_id']}/download"}
        finally:
            await file.close()

    app.state.expiry_tasks = set()

    @app.get('/api/v1/sessions/{session_id}/download')
    async def download(session_id: str):
        result = await run_in_threadpool(store.get, session_id)
        if result is None:
            raise HTTPException(404, 'Phiên đã hết hạn hoặc đã bị xóa. Hãy tải lại tệp gốc.')
        record, path = result
        # Results can be downloaded again until deleted or expired.
        return FileResponse(path, filename=record['filename'], media_type=MIME)

    @app.delete('/api/v1/sessions/{session_id}', status_code=204)
    async def delete(session_id: str):
        await run_in_threadpool(store.delete, session_id)

    app.mount('/static', StaticFiles(directory=BASE / 'static'), name='static')

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(BASE / 'static/index.html')

    return app

app = create_app()
