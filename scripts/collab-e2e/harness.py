"""
Arnés de integración del canal de colaboración (Nivel B).

Un proxy TCP que se puede cortar y reponer delante de un uvicorn real, más una API de
administración mínima (HTTP, con CORS) que usa el spec que corre en el navegador. Lo arranca
`run.py`; ver README.md.

    python scripts/collab-e2e/harness.py --target-port 8939 --proxy-port 8940 \
        --admin-port 8941 --config config.json --db shared.db

API de administración (GET):
    /config   la configuración sembrada por run.py (tokens, ids)
    /cut      corta: aborta las conexiones abiertas y rechaza las nuevas (el navegador ve 1006)
    /restore  repone el paso
    /stats    conexiones TCP aceptadas / rechazadas / abiertas
    /reset    pone a cero los contadores
    /revoke   borra la fila del Colaborador (simula que le retiran el acceso)
"""

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROXY_HOST = "127.0.0.1"


class TcpProxy:
    def __init__(self, listen_port: int, target_port: int) -> None:
        self.listen_port = listen_port
        self.target_port = target_port
        self.cut = False
        self.accepted = 0  # conexiones TCP aceptadas (incluidas las rechazadas por estar cortado)
        self.refused = 0
        self._writers: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        await asyncio.start_server(self._handle, PROXY_HOST, self.listen_port)

    async def _handle(
        self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ) -> None:
        self.accepted += 1
        if self.cut:
            self.refused += 1
            client_writer.transport.abort()
            return
        try:
            up_reader, up_writer = await asyncio.open_connection(PROXY_HOST, self.target_port)
        except OSError:
            client_writer.transport.abort()
            return
        pair = (client_writer, up_writer)
        self._writers.update(pair)

        async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                while data := await reader.read(65536):
                    writer.write(data)
                    await writer.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                writer.close()

        try:
            await asyncio.gather(pipe(client_reader, up_writer), pipe(up_reader, client_writer))
        finally:
            self._writers.difference_update(pair)

    def cut_all(self) -> None:
        self.cut = True
        for writer in list(self._writers):
            writer.transport.abort()  # cierre abrupto: el navegador ve 1006, sin frame de cierre
        self._writers.clear()

    def restore(self) -> None:
        self.cut = False

    def stats(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "refused": self.refused,
            "open": len(self._writers) // 2,
            "cut": self.cut,
        }

    def reset(self) -> None:
        self.accepted = 0
        self.refused = 0


def revoke_collaborator(db_path: str, canvas_id: str, user_id: str) -> int:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM canvas_collaborators WHERE canvas_id = ? AND user_id = ?",
            (canvas_id, user_id),
        )
        return cursor.rowcount


async def serve_admin(
    proxy: TcpProxy, config: dict[str, Any], db_path: str, admin_port: int
) -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode("latin-1")
            while await reader.readline() not in (b"\r\n", b"\n", b""):
                pass  # se descartan las cabeceras
            method, target, *_ = request_line.split(" ")
            path = urlparse(target).path
            status, body = 200, None
            if method != "OPTIONS":
                if path == "/config":
                    body = config
                elif path == "/cut":
                    proxy.cut_all()
                    body = proxy.stats()
                elif path == "/restore":
                    proxy.restore()
                    body = proxy.stats()
                elif path == "/stats":
                    body = proxy.stats()
                elif path == "/reset":
                    proxy.reset()
                    body = proxy.stats()
                elif path == "/revoke":
                    body = {
                        "deleted": revoke_collaborator(
                            db_path, config["canvasId"], config["collaboratorUserId"]
                        )
                    }
                else:
                    status, body = 404, {"error": "ruta desconocida"}
            payload = json.dumps(body).encode() if body is not None else b""
            writer.write(
                (
                    f"HTTP/1.1 {status} OK\r\n"
                    "Access-Control-Allow-Origin: *\r\n"
                    "Access-Control-Allow-Headers: *\r\n"
                    "Access-Control-Allow-Methods: GET, OPTIONS\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(payload)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
                + payload
            )
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()

    await asyncio.start_server(handle, PROXY_HOST, admin_port)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--target-port", type=int, required=True)
    parser.add_argument("--proxy-port", type=int, required=True)
    parser.add_argument("--admin-port", type=int, required=True)
    parser.add_argument("--config", required=True, help="JSON con tokens e ids sembrados")
    parser.add_argument("--db", required=True, help="ruta del SQLite del backend (para /revoke)")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    proxy = TcpProxy(args.proxy_port, args.target_port)
    await proxy.start()
    await serve_admin(proxy, config, args.db, args.admin_port)
    print(f"proxy :{args.proxy_port} -> :{args.target_port}; admin :{args.admin_port}", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
