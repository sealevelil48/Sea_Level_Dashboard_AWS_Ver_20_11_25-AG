#!/usr/bin/env python
"""
On-prem / local launcher for the Sea Level Dashboard.

All API routes live in app.py (shared with AWS Lambda). This file only:
  * loads backend/.env
  * serves the React production build (frontend/build) for non-API paths
  * starts uvicorn

Environment (backend/.env):
  BACKEND_PORT=30886  HOST=0.0.0.0
  AUTH_MODE=cognito   COGNITO_REGION / COGNITO_USER_POOL_ID / COGNITO_APP_CLIENT_ID / ADMIN_EMAILS
  AUTH_MODE=disabled  → local development only; calibration stays locked unless
                        ALLOW_INSECURE_LOCAL_CALIBRATION=true (never on a shared server)
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent
load_dotenv(BACKEND_ROOT / ".env")
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app import app, logger  # noqa: E402

FRONTEND_BUILD = (BACKEND_ROOT.parent / "frontend" / "build").resolve()

if (FRONTEND_BUILD / "index.html").exists():
    if (FRONTEND_BUILD / "static").is_dir():
        app.mount("/static", StaticFiles(directory=FRONTEND_BUILD / "static"), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (FRONTEND_BUILD / full_path).resolve()
        # Only serve real files inside the build directory; everything else → SPA shell.
        if full_path and candidate.is_file() and FRONTEND_BUILD in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_BUILD / "index.html")
else:
    logger.warning("Frontend build not found at %s — serving API only", FRONTEND_BUILD)


if __name__ == "__main__":
    import uvicorn

    if sys.platform == "win32":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "30886"))
    logger.info("Sea Level Dashboard on http://%s:%s (auth=%s)", host, port, os.getenv("AUTH_MODE", "cognito"))
    uvicorn.run(app, host=host, port=port, log_level="info", workers=1, loop="asyncio")
