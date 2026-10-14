"""Container entry point: python -m app.serve

Runs `python -m app.publish --check` first and starts the server only if the publication store is
current. A broken checkout therefore never comes up as a running container. The port is read from
PORT (default 8000). Request tracing to Application Insights starts only if
APPLICATIONINSIGHTS_CONNECTION_STRING is set (app/telemetry.py).
"""

from __future__ import annotations

import os
import sys

from app import telemetry
from app.publish.__main__ import main as publish_check

DEFAULT_PORT = 8000


def main() -> int:
    if publish_check(["--check"]) != 0:
        print("startup check failed: the publication store is out of date or unreadable; "
              "not starting the server", file=sys.stderr)
        return 1
    telemetry.setup()  # before the app module is imported, so FastAPI is instrumented; no-op without a connection string
    import uvicorn

    uvicorn.run("app.api.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", DEFAULT_PORT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
