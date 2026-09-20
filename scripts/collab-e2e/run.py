"""
Orquestador del Nivel B: un uvicorn real + el arnés (proxy cortable) + Karma en un navegador real.

    python scripts/collab-e2e/run.py

Levanta el backend con una base SQLite temporal, siembra usuarios y un Lienzo, arranca el proxy y
ejecuta solo los specs `*.integration.spec.ts` del frontend en Edge/Chrome headless. Ver README.md.
"""

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "front_generador_bd"
BACKEND_PORT, PROXY_PORT, ADMIN_PORT = 8939, 8940, 8941
BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def find_browser() -> str:
    from_env = os.environ.get("CHROME_BIN")
    if from_env and Path(from_env).exists():
        return from_env
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    sys.exit("No encuentro Chrome ni Edge: define CHROME_BIN con la ruta de un navegador Chromium.")


def http(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{BACKEND_PORT}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode(errors="replace")


def wait_for(url: str, seconds: int = 30) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except OSError:
            time.sleep(0.4)
    sys.exit(f"No respondió a tiempo: {url}")


def register(prefix: str) -> tuple[str, dict]:
    status, body = http(
        "POST",
        "/api/v2/auth/register",
        {
            "email": f"{prefix}-{uuid.uuid4().hex[:8]}@collab-e2e.dev",
            "password": "Password123!",
            "fullName": prefix.capitalize(),
        },
    )
    assert status == 201, (status, body)
    return body["accessToken"], body["user"]


def seed(secret: str) -> dict:
    sys.path.insert(0, str(REPO))
    os.environ["JWT_SECRET"] = secret
    from backend_case.app.shared.security.tokens import create_access_token

    owner_token, owner = register("owner")
    outsider_token, _ = register("outsider")
    collaborator_token, collaborator = register("collaborator")
    peer_token, _ = register("peer")
    status, canvas = http("POST", "/api/v2/canvases", {"name": "Collab E2E"}, owner_token)
    assert status == 201, (status, canvas)
    status, joined = http(
        "POST", "/api/v2/canvases/join", {"accessCode": canvas["roomName"]}, collaborator_token
    )
    assert status == 200, (status, joined)
    status, joined = http(
        "POST", "/api/v2/canvases/join", {"accessCode": canvas["roomName"]}, peer_token
    )
    assert status == 200, (status, joined)
    expired = create_access_token(
        owner["id"], owner["email"], owner["fullName"], expires_delta=timedelta(seconds=-5)
    )
    return {
        "wsBase": f"ws://127.0.0.1:{PROXY_PORT}",
        "httpBase": f"http://127.0.0.1:{BACKEND_PORT}",
        "canvasId": canvas["id"],
        "collaboratorUserId": collaborator["id"],
        "tokens": {
            "owner": owner_token,
            "outsider": outsider_token,
            "collaborator": collaborator_token,
            # Segundo Colaborador que NINGÚN test revoca (la escena 4 revoca al anterior): es el
            # "Beto" de los tests de sincronización, cuyo orden de ejecución es aleatorio.
            "peer": peer_token,
            "expiredOwner": expired,
        },
    }


def main() -> int:
    browser = find_browser()
    workdir = Path(tempfile.mkdtemp(prefix="collab-e2e-"))
    db_path = (workdir / "collab_e2e.db").as_posix()
    secret = secrets.token_urlsafe(32)
    env = dict(os.environ, JWT_SECRET=secret, PYTHONPATH=str(REPO), PYTHONIOENCODING="utf-8")
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    procs: list[subprocess.Popen] = []
    files = ExitStack()
    backend_log = files.enter_context((workdir / "backend.log").open("w"))
    harness_log = files.enter_context((workdir / "harness.log").open("w"))
    try:
        backend = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend_case.app.main:app",
                "--port",
                str(BACKEND_PORT),
                "--log-level",
                "warning",
            ],
            cwd=workdir,
            env=env,
            stdout=backend_log,
            stderr=subprocess.STDOUT,
        )
        procs.append(backend)
        wait_for(f"http://127.0.0.1:{BACKEND_PORT}/docs")
        config = seed(secret)
        (workdir / "config.json").write_text(json.dumps(config), encoding="utf-8")

        harness = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).with_name("harness.py")),
                "--target-port",
                str(BACKEND_PORT),
                "--proxy-port",
                str(PROXY_PORT),
                "--admin-port",
                str(ADMIN_PORT),
                "--config",
                str(workdir / "config.json"),
                "--db",
                db_path,
            ],
            stdout=harness_log,
            stderr=subprocess.STDOUT,
        )
        procs.append(harness)
        wait_for(f"http://127.0.0.1:{ADMIN_PORT}/config")

        npx = shutil.which("npx") or "npx"
        karma = subprocess.run(
            [
                npx,
                "ng",
                "test",
                "--watch=false",
                "--browsers=ChromeHeadless",
                "--include",
                "src/app/**/*.integration.spec.ts",
            ],
            cwd=FRONTEND,
            env=dict(os.environ, CHROME_BIN=browser),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines = [ln for ln in karma.stdout.splitlines() if "Executed" not in ln or "TOTAL" in ln]
        summary = [
            ln
            for ln in karma.stdout.replace("\r", "\n").splitlines()
            if "TOTAL" in ln or "FAILED" in ln or "Error" in ln
        ]
        print("\n".join(lines[-25:]) if karma.returncode else "")
        print("\n".join(dict.fromkeys(summary)) or karma.stdout[-1500:])
        return karma.returncode
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
        files.close()
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
