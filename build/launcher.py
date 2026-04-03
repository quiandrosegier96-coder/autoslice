"""
AutoSlice Desktop Launcher
Starts the backend (FastAPI) + frontend (Next.js) then shows them
inside a native Windows window using pywebview (Edge WebView2).
No browser needed — looks and feels like a real desktop app.
"""

import os
import sys
import time
import subprocess
import threading
import urllib.request

try:
    import webview  # pywebview — native window
except Exception as _e:
    import os, traceback
    _log = os.path.join(os.path.dirname(sys.executable) if getattr(sys,"frozen",False) else os.path.dirname(os.path.abspath(__file__)), "crash.log")
    open(_log,"w").write(traceback.format_exc())
    raise

# ── Paths ────────────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

BACKEND_EXE  = os.path.join(BASE, "backend", "autoslice_backend.exe")
NODE_EXE     = os.path.join(BASE, "node",    "node.exe")
SERVER_JS    = os.path.join(BASE, "frontend", "server.js")
FRONTEND_DIR = os.path.join(BASE, "frontend")

BACKEND_URL  = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

LOADING_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#111;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif}
.spinner{width:48px;height:48px;border:3px solid #333;border-top-color:#e02424;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 20px}
@keyframes spin{to{transform:rotate(360deg)}}
h1{color:#fff;font-size:22px;font-weight:700;margin-bottom:6px}
p{color:#555;font-size:13px}.c{text-align:center}
</style></head><body>
<div class="c"><div class="spinner"></div><h1>AutoSlice</h1><p>Starting...</p></div>
</body></html>"""

_backend_proc  = None
_frontend_proc = None


def _wait_for_http(url: str, timeout: int = 60) -> bool:
    for _ in range(timeout):
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def _start_servers():
    global _backend_proc, _frontend_proc

    log_dir = os.path.join(os.environ.get("APPDATA", BASE), "AutoSlice", "logs")
    os.makedirs(log_dir, exist_ok=True)
    backend_log  = open(os.path.join(log_dir, "backend.log"),  "w")
    frontend_log = open(os.path.join(log_dir, "frontend.log"), "w")

    appdata = os.environ.get("APPDATA", BASE)
    user_dir = os.path.join(appdata, "AutoSlice")
    os.makedirs(user_dir, exist_ok=True)

    env = os.environ.copy()
    env["PORT"]              = "3000"
    env["HOSTNAME"]          = "127.0.0.1"
    env["AUTOSLICE_DATA_DIR"] = os.path.join(BASE, "backend", "_internal", "data")
    env["UPLOAD_DIR"]        = os.path.join(user_dir, "temp")
    env["DB_PATH"]           = os.path.join(user_dir, "autoslice.db")

    _backend_proc = subprocess.Popen(
        [BACKEND_EXE],
        cwd=os.path.join(BASE, "backend"),
        env=env,
        stdout=backend_log,
        stderr=backend_log,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    _frontend_proc = subprocess.Popen(
        [NODE_EXE, SERVER_JS],
        cwd=FRONTEND_DIR,
        env=env,
        stdout=frontend_log,
        stderr=frontend_log,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _stop_servers():
    for proc in (_backend_proc, _frontend_proc):
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass


def main():
    # Start servers in background
    t = threading.Thread(target=_start_servers, daemon=True)
    t.start()

    # Show a loading window while servers start
    window = webview.create_window(
        title="AutoSlice",
        html=LOADING_HTML,
        width=1280,
        height=820,
        min_size=(900, 600),
        text_select=True,
    )

    def _load_when_ready():
        # Wait for frontend to be up then navigate
        _wait_for_http(FRONTEND_URL + "/api/health", timeout=60)
        time.sleep(1)
        window.load_url(FRONTEND_URL)

    threading.Thread(target=_load_when_ready, daemon=True).start()

    webview.start(
        gui="edgechromium",   # use Edge WebView2 (built into Windows 11)
        debug=False,
    )

    # Window closed — stop servers
    _stop_servers()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        err = traceback.format_exc()
        print(err)
        # also write to file
        try:
            log_path = os.path.join(BASE, "crash.log")
            open(log_path, "w").write(err)
        except Exception:
            pass
        input("Press Enter to close...")  # keep window open so you can read the error
