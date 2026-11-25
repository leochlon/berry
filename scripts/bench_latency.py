"""How long does one claim check take? Runs against a local imitation of an OpenAI-compatible
server with a realistic connection-setup delay and response delay, so it needs no API key.

  PYTHONPATH=src python scripts/bench_latency.py [claims] [connect_s] [response_s]

Compare two checkouts by pointing PYTHONPATH at each.
"""

from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CLAIMS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
CONNECT_S = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25  # DNS + TLS for a new connection
RESPONSE_S = float(sys.argv[3]) if len(sys.argv) > 3 else 0.9  # time for the model to answer


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # keep-alive: an open connection is reused

    def setup(self) -> None:
        time.sleep(CONNECT_S)  # a new connection pays the setup cost once
        super().setup()

    def log_message(self, *a) -> None:
        pass

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        time.sleep(RESPONSE_S)
        redacted = "[REDACTED]" in json.dumps(body)
        p = 0.05 if redacted else 0.97
        tok = lambda t, lp: {"token": t, "logprob": lp, "bytes": None}
        resp = {
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{
                "index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "YES"},
                "logprobs": {"content": [{
                    "token": "YES", "logprob": math.log(p), "bytes": None,
                    "top_logprobs": [tok("YES", math.log(p)), tok("NO", math.log(1 - p))],
                }]},
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        out = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{server.server_port}/v1"
    os.environ["OPENAI_API_KEY"] = "bench"
    from berry.hallucination_detector import run_audit_trace_budget

    steps = [{"idx": i, "claim": f"Claim number {i} about the question.", "cites": ["Q"]} for i in range(CLAIMS)]
    spans = [{"sid": "Q", "text": 'The user\'s request, quoted exactly: "What was revenue in 2026?".'}]
    import berry

    print(f"berry from: {os.path.dirname(berry.__file__)}")
    print(f"{CLAIMS} claims = {2 * CLAIMS} verifier calls | connect {CONNECT_S}s, response {RESPONSE_S}s")
    for run in (1, 2):  # the second run shows what a warm process costs
        t0 = time.perf_counter()
        result = run_audit_trace_budget(steps=steps, spans=spans, verifier_model="m", default_target=0.9)
        print(f"  run {run}: {time.perf_counter() - t0:.2f}s  flagged={sum(d['flagged'] for d in result['details'])}")


if __name__ == "__main__":
    main()
