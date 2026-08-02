#!/usr/bin/env python3
"""
Sojus Pipeline — OpenAI-kompatibler Bridge von Open WebUI zu n8n Firmenchef.
Open WebUI sieht diesen Server als "KI-Modell". Die echte Intelligenz liegt in n8n.
"""

import json
import os
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError

N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL",
    "http://localhost:5678/webhook/sojus-firmenchef"
)
PIPELINE_API_KEY = os.environ.get("PIPELINE_API_KEY", "sojus-pipeline-key")
PORT = int(os.environ.get("PIPELINE_PORT", "3001"))

STUB_RESPONSE = (
    "Sojus ist bereit und wartet auf seinen Einsatz! 🚀\n\n"
    "Die Infrastruktur läuft, aber der n8n-Firmenchef ist noch nicht aktiv "
    "oder der Kalender-Spezialist braucht noch einen Moment. "
    "Schau mal in n8n ob der Workflow 'sojus-firmenchef' läuft."
)


class PipelineHandler(BaseHTTPRequestHandler):
    def _check_auth(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        return auth[7:] == PIPELINE_API_KEY

    def _send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/models":
            self._send_json(200, {
                "object": "list",
                "data": [{
                    "id": "sojus-agent",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "sojus",
                    "display_name": "Sojus (n8n Agent)"
                }]
            })
        elif self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return

        messages = body.get("messages", [])
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            ""
        )
        # Letzten 10 Nachrichten als History
        history = [
            f"{m['role']}: {m['content']}"
            for m in messages[:-1]
        ][-10:]

        response_text = self._call_n8n(last_user, history)

        self._send_json(200, {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "sojus-agent",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        })

    def _call_n8n(self, message, history):
        payload = json.dumps({
            "message": message,
            "history": history,
            "request_id": str(uuid.uuid4()),
            "user": "fuchs",
            "channel": "open_webui"
        }).encode()

        req = Request(
            N8N_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                return result.get("response", result.get("message", str(result)))
        except URLError as e:
            return STUB_RESPONSE
        except Exception as e:
            return f"⚠️ Pipeline-Fehler: {e}"

    def log_message(self, format, *args):
        # Nur Fehler loggen, kein Access-Log-Spam
        if "ERROR" in (args[1] if len(args) > 1 else ""):
            super().log_message(format, *args)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), PipelineHandler)
    print(f"Sojus Pipeline auf Port {PORT} — N8N: {N8N_WEBHOOK_URL}")
    server.serve_forever()
