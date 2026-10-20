"""Local desktop launcher; never stops a process already using the selected port."""

import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser
import uvicorn
from v1.diagnostics import BUILD


def main():
    os.chdir(Path(__file__).resolve().parent)
    try:
        port = int(os.environ.get("DOCLINT_PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        print("DOCLINT_PORT phải là số từ 1 đến 65535.")
        return 1
    address = f"http://127.0.0.1:{port}"
    with socket.socket() as probe:
        in_use = probe.connect_ex(("127.0.0.1", port)) == 0
    if in_use:
        try:
            with urlopen(address + "/api/v1/capabilities", timeout=2) as response:
                cap = json.load(response)
            if cap.get("version") == "1.0" and cap.get("build") == BUILD:
                print("DocLint V1 đang chạy; mở lại cửa sổ trình duyệt.")
                webbrowser.open(address)
                return 0
        except (URLError, ValueError):
            pass
        print(
            f"Cổng {port} đang được dùng. Dừng Terminal DocLint cũ bằng Ctrl+C, rồi chạy lại."
        )
        return 1
    from v1.renderer import find_office

    if not find_office():
        print(
            "Chưa tìm thấy LibreOffice. Cài bản miễn phí từ libreoffice.org để có PDF trước–sau và kiểm tra trang."
        )
        print("Web vẫn chạy; các chức năng cần bộ dựng sẽ được báo chưa hoàn tất.")

    def open_when_ready():
        for _ in range(100):
            try:
                with urlopen(address + "/api/v1/health", timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(address)
                        return
            except URLError:
                time.sleep(0.2)

    threading.Thread(target=open_when_ready, daemon=True).start()
    print("Giữ cửa sổ này mở trong lúc sử dụng. Nhấn Ctrl+C để dừng.")
    uvicorn.run("api:app", host="127.0.0.1", port=port, access_log=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
