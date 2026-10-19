"""Short-lived download sessions. Originals are never written to this store."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time
from uuid import UUID, uuid4

TTL_SECONDS = 30 * 60

class SessionStore:
    def __init__(self, root, ttl=TTL_SECONDS):
        self.root = Path(root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.ttl = ttl

    def create(self, data, filename, report):
        session_id = str(uuid4())
        folder = self.root / session_id
        folder.mkdir(mode=0o700)
        expires = time.time() + self.ttl
        record = {'session_id': session_id, 'filename': filename, 'expires': expires,
                  'expires_at': datetime.fromtimestamp(expires, timezone.utc).isoformat(), **report}
        try:
            (folder / 'result.docx').write_bytes(data)
            (folder / 'report.json').write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return record

    def _folder(self, session_id):
        if str(UUID(session_id)) != session_id:
            raise ValueError('Invalid session')
        return self.root / session_id

    def get(self, session_id):
        try:
            folder = self._folder(session_id)
            record = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
            if record['expires'] <= time.time():
                self.delete(session_id)
                return None
            if not (folder / 'result.docx').is_file():
                return None
            return record, folder / 'result.docx'
        except (ValueError, FileNotFoundError, KeyError):
            return None

    def delete(self, session_id):
        try:
            shutil.rmtree(self._folder(session_id), ignore_errors=True)
        except ValueError:
            pass

    def cleanup(self):
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue
            try:
                self._folder(folder.name)
            except ValueError:
                continue  # Do not touch unrelated directories.
            try:
                record = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
                expired = float(record['expires']) <= time.time()
            except (ValueError, FileNotFoundError, KeyError, TypeError):
                try:
                    expired = folder.stat().st_mtime + self.ttl <= time.time()
                except FileNotFoundError:
                    continue  # Another worker or an explicit delete already removed it.
            if expired:
                self.delete(folder.name)
