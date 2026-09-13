import json
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend_case.app.legacy.services_gemini import call_gemini_analysis
from backend_case.app.legacy.signaling_manager import signaling_manager

legacy_ws_router = APIRouter(tags=["Legacy Compatibility WebSockets"])


# 1. Canvas Signaling WebSocket
@legacy_ws_router.websocket("/ws/canvas/{room_name}/")
@legacy_ws_router.websocket("/ws/canvas/{room_name}")
async def canvas_websocket(websocket: WebSocket, room_name: str):
    peer_id = await signaling_manager.connect(websocket, room_name)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
            except Exception:
                continue
            await signaling_manager.handle_message(room_name, peer_id, data)
    except WebSocketDisconnect:
        await signaling_manager.disconnect(room_name, peer_id)
    except Exception:
        await signaling_manager.disconnect(room_name, peer_id)


# 2. UML Validation WebSocket
@legacy_ws_router.websocket("/ws/uml/")
@legacy_ws_router.websocket("/ws/uml")
async def uml_validation_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
            except Exception:
                continue

            action = data.get("action")
            if action == "validate_model":
                uml_json = data.get("uml")
                prompt = f"""
Eres un experto en diseño de bases de datos.
Analiza si las relaciones de este UML son correctas en base a los nombres y atributos.

JSON UML:
{json.dumps(uml_json, indent=2)}
"""
                raw_output = call_gemini_analysis(prompt)

                if isinstance(raw_output, str):
                    raw_output = re.sub(
                        r"^```json\s*|\s*```$", "", raw_output.strip(), flags=re.MULTILINE
                    )

                try:
                    analysis = json.loads(raw_output)
                except Exception:
                    analysis = {"error": "Formato inválido", "raw": raw_output}

                await websocket.send_text(
                    json.dumps(
                        {
                            "action": "validation_result",
                            "analysis": analysis,
                        },
                        ensure_ascii=False,
                    )
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
