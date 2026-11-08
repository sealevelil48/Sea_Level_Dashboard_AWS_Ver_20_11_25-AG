"""
Sea Level Dashboard API — one FastAPI app for every environment.

  * AWS:      lambda_entry.handler (Mangum) behind API Gateway REST + Cognito authorizer
  * On-prem:  local_server_optimized.py (uvicorn) — also serves the React build

Every /api route except /api/health and the two map iframes requires a signed-in user.
Calibration and maintenance routes require an admin (see shared/auth.py).

Route handlers are plain `def` on purpose: the data handlers are synchronous (SQLAlchemy),
and FastAPI runs `def` routes in a threadpool, so one slow query no longer blocks others.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from shared.auth import (  # noqa: E402
    AuthError, Identity, auth_mode, identity_from_claims, identity_from_event, verify_bearer_token,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stdout)
logger = logging.getLogger("sea-level-api")

CALIBRATION_ENABLED = os.getenv("CALIBRATION_ENABLED", "true").lower() == "true"
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Handlers (import failures are logged and surface as 503, never crash the app)
# ---------------------------------------------------------------------------

def _unavailable(name):
    def handler(event, context=None):
        return {"statusCode": 503, "body": json.dumps({"error": f"{name} unavailable"})}
    return handler


def _import(module: str, attr: str):
    try:
        mod = __import__(module, fromlist=[attr])
        return getattr(mod, attr)
    except Exception as exc:  # pragma: no cover - depends on deployment
        logger.error("Could not import %s.%s: %s", module, attr, exc)
        return _unavailable(f"{module}.{attr}")


get_stations_handler = _import("lambdas.get_stations.main", "lambda_handler")
get_data_handler = _import("lambdas.get_data.main", "lambda_handler")
get_data_batch_handler = _import("lambdas.get_data.main", "lambda_handler_batch")
get_live_data_handler = _import("lambdas.get_live_data.main", "lambda_handler")
get_predictions_handler = _import("lambdas.get_predictions.main", "lambda_handler")
get_ims_warnings_handler = _import("lambdas.get_ims_warnings.main", "lambda_handler")
get_station_map_handler = _import("lambdas.get_station_map.main", "lambda_handler")
get_analytics_handler = _import("lambdas.get_analytics.main", "lambda_handler")
build_forecast_payload = _import("lambdas.get_sea_forecast.main", "build_forecast_payload")

if CALIBRATION_ENABLED:
    from lambdas.calibration import main as calibration  # noqa: E402
else:
    calibration = None

try:
    from shared.database_production import db_manager
except Exception as exc:  # pragma: no cover
    logger.error("Database manager unavailable: %s", exc)
    db_manager = None

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Sea Level Dashboard API",
    version="3.0.0",
    docs_url="/api/docs" if ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if ENABLE_DOCS else None,
)

_cors = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip() and o.strip() != "*"]
if _cors:
    app.add_middleware(CORSMiddleware, allow_origins=_cors, allow_credentials=False,
                       allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.startswith("/api/") and not request.url.path.endswith("mapframe"):
        response.headers.setdefault("Cache-Control", "private, no-store")
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse({"error": "Internal server error"}, status_code=500)

# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------

def current_user(request: Request) -> Identity:
    if auth_mode() == "disabled":
        return identity_from_event({})
    aws_event = request.scope.get("aws.event")
    if aws_event is not None:
        # API Gateway's Cognito authorizer already validated the token.
        ident = identity_from_event(aws_event)
    else:
        try:
            ident = identity_from_claims(verify_bearer_token(request.headers.get("authorization")))
        except AuthError as exc:
            logger.info("Auth rejected: %s", exc)
            ident = None
    if ident is None:
        raise HTTPException(status_code=401, detail="Sign-in required")
    request.state.identity = ident
    return ident


def admin_user(user: Identity = Depends(current_user)) -> Identity:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def _event(path: str, params: Optional[Dict[str, Any]] = None, user: Optional[Identity] = None,
           body: Any = None, method: str = "GET") -> Dict[str, Any]:
    """Build an API-Gateway-shaped event for the shared handlers, including verified claims."""
    event: Dict[str, Any] = {
        "httpMethod": method, "path": path,
        "queryStringParameters": {k: v for k, v in (params or {}).items() if v is not None},
    }
    if body is not None:
        event["body"] = body
    if user is not None:
        event["requestContext"] = {"authorizer": {"claims": {
            "sub": user.sub, "email": user.email, "email_verified": str(user.email_verified).lower(),
            "cognito:groups": user.groups,
        }}}
    return event


_HOP_HEADERS = {"access-control-allow-origin", "content-length", "content-type"}


def _respond(lambda_response: Dict[str, Any], cache: Optional[str] = None) -> JSONResponse:
    status = int(lambda_response.get("statusCode", 200))
    body = lambda_response.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = {"data": body}
    if status >= 500 and isinstance(body, dict) and "error" in body:
        body = {"error": "Internal server error"}  # never leak internals
    headers = {k: v for k, v in (lambda_response.get("headers") or {}).items() if k.lower() not in _HOP_HEADERS}
    if cache and status == 200:
        headers["Cache-Control"] = cache
    return JSONResponse(content=body, status_code=status, headers=headers)


PRIVATE_SHORT = "private, no-cache"   # data can change (sync every minute, calibration); always revalidate
PRIVATE_LONG = "private, max-age=600"

# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    status = {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}
    try:
        status["database"] = "ok" if db_manager and db_manager.health_check() else "unavailable"
    except Exception:
        status["database"] = "unavailable"
    return status


@app.get("/api/mapframe", include_in_schema=False)
@app.get("/mapframe", include_in_schema=False)
def mapframe():
    return FileResponse(BACKEND_ROOT / "mapframe.html", media_type="text/html")


@app.get("/api/mariners-mapframe", include_in_schema=False)
def mariners_mapframe():
    return FileResponse(BACKEND_ROOT / "mariners_mapframe.html", media_type="text/html")

# ---------------------------------------------------------------------------
# Signed-in routes
# ---------------------------------------------------------------------------

@app.get("/api/me")
def me(user: Identity = Depends(current_user)):
    return user.to_public()


@app.get("/api/stations")
def stations(user: Identity = Depends(current_user)):
    return _respond(get_stations_handler(_event("/stations"), None), "private, max-age=1800")


@app.get("/api/data")
def data(station: str = Query("All Stations", max_length=200),
         start_date: Optional[str] = Query(None, max_length=40), end_date: Optional[str] = Query(None, max_length=40),
         data_source: str = Query("default", max_length=20), limit: int = Query(1000, ge=1, le=5000),
         page: int = Query(1, ge=1), user: Identity = Depends(current_user)):
    params = {"station": station, "start_date": start_date, "end_date": end_date, "data_source": data_source,
              "limit": str(limit), "page": str(page)}
    return _respond(get_data_handler(_event("/data", params), None), PRIVATE_SHORT)


@app.get("/api/data/batch")
def data_batch(stations: Optional[str] = Query(None, max_length=500),
               start_date: Optional[str] = Query(None, max_length=40), end_date: Optional[str] = Query(None, max_length=40),
               data_source: str = Query("default", max_length=20), show_anomalies: bool = False,
               include_outliers: bool = False, user: Identity = Depends(current_user)):
    params = {"stations": stations, "start_date": start_date, "end_date": end_date, "data_source": data_source,
              "show_anomalies": str(show_anomalies).lower(), "include_outliers": str(include_outliers).lower()}
    return _respond(get_data_batch_handler(_event("/data/batch", params), None), PRIVATE_SHORT)


@app.get("/api/live-data")
@app.get("/api/latest")
def live_data(station: Optional[str] = Query(None, max_length=50), limit: int = Query(100, ge=1, le=1000),
              user: Identity = Depends(current_user)):
    return _respond(get_live_data_handler(_event("/live-data", {"station": station, "limit": str(limit)}), None),
                    PRIVATE_SHORT)


@app.get("/api/predictions")
def predictions(stations: Optional[str] = Query(None, max_length=500), station: Optional[str] = Query(None, max_length=50),
                model: str = Query("kalman", max_length=20), steps: int = Query(240, ge=1, le=2000),
                forecast_hours: Optional[int] = Query(None, ge=1, le=2000), user: Identity = Depends(current_user)):
    target = stations or station
    if not target:
        raise HTTPException(status_code=400, detail="Station parameter is required")
    n = forecast_hours or steps
    params = {"stations": target, "station": target, "model": model, "steps": str(n)}
    return _respond(get_predictions_handler(_event("/predictions", params), None), PRIVATE_LONG)


@app.get("/api/analytics")
def analytics(analysis_type: str = Query("rolling_avg", max_length=30), station: Optional[str] = Query(None, max_length=50),
              station1: Optional[str] = Query(None, max_length=50), station2: Optional[str] = Query(None, max_length=50),
              start_date: Optional[str] = Query(None, max_length=40), end_date: Optional[str] = Query(None, max_length=40),
              window_hours: str = Query("3,6,24", max_length=40), period_days: Optional[int] = Query(None, ge=1, le=3650),
              lag_hours: int = Query(1, ge=-720, le=720), user: Identity = Depends(current_user)):
    params = {"analysis_type": analysis_type, "station": station, "station1": station1, "station2": station2,
              "start_date": start_date, "end_date": end_date, "window_hours": window_hours,
              "period_days": str(period_days) if period_days else None, "lag_hours": str(lag_hours)}
    return _respond(get_analytics_handler(_event("/analytics", params), None), PRIVATE_SHORT)


@app.get("/api/export")
def export(station: str = Query("All Stations", max_length=200),
           start_date: Optional[str] = Query(None, max_length=40), end_date: Optional[str] = Query(None, max_length=40),
           fmt: str = Query("csv", pattern="^(csv|json)$"), user: Identity = Depends(current_user)):
    """CSV/JSON export of the (corrected) series → S3 presigned URL (AWS) or direct download (on-prem)."""
    from fastapi.responses import Response
    from shared.exports import store
    resp = get_data_handler(_event("/data", {"station": station, "start_date": start_date, "end_date": end_date,
                                              "data_source": "default", "limit": "5000"}), None)
    if int(resp.get("statusCode", 500)) != 200:
        return _respond(resp)
    records = json.loads(resp["body"]) if isinstance(resp.get("body"), str) else resp.get("body")
    if not isinstance(records, list):
        records = []
    url, filename, body = store(records, fmt, station, user.sub)
    logger.info("export station=%s rows=%s fmt=%s user=%s", station, len(records), fmt, user.sub)
    if url:
        return {"url": url, "filename": filename, "rows": len(records), "expires_in_seconds": 900}
    return Response(body, media_type="text/csv" if fmt == "csv" else "application/json",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/stations/map")
@app.get("/stations/map", include_in_schema=False)
def stations_map(end_date: Optional[str] = Query(None, max_length=40), user: Identity = Depends(current_user)):
    return _respond(get_station_map_handler(_event("/stations/map", {"end_date": end_date}), None), PRIVATE_SHORT)


@app.get("/api/sea-forecast")
@app.get("/sea-forecast", include_in_schema=False)
def sea_forecast(user: Identity = Depends(current_user)):
    return JSONResponse(build_forecast_payload(), headers={"Cache-Control": "private, max-age=1800"})


@app.get("/api/ims-warnings")
def ims_warnings(user: Identity = Depends(current_user)):
    return _respond(get_ims_warnings_handler(_event("/ims-warnings"), None), "private, max-age=600")


@app.get("/api/mariners-forecast")
def mariners_forecast(user: Identity = Depends(current_user)):
    from shared.ims_mariners import fetch_mariners_forecast
    try:
        return JSONResponse(fetch_mariners_forecast(), headers={"Cache-Control": "private, max-age=1800"})
    except Exception:
        logger.exception("Mariners forecast failed")
        raise HTTPException(status_code=502, detail="IMS mariners forecast unavailable")


@app.get("/api/outliers")
@app.get("/api/outliers/optimized")
def outliers(start_date: Optional[str] = Query(None, max_length=40), end_date: Optional[str] = Query(None, max_length=40),
             station: str = Query("All Stations", max_length=50), use_cache: bool = True,
             user: Identity = Depends(current_user)):
    from shared.southern_baseline_api import SouthernBaselineAPI
    result = SouthernBaselineAPI(db_manager).get_outliers(start_date=start_date, end_date=end_date,
                                                          station=station, use_cache=use_cache)
    return JSONResponse(result, headers={"Cache-Control": PRIVATE_SHORT})

# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.get("/api/metrics")
def metrics(user: Identity = Depends(admin_user)):
    return {"timestamp": datetime.now(timezone.utc).isoformat(),
            "database": db_manager.get_metrics() if db_manager and hasattr(db_manager, "get_metrics") else {}}


@app.post("/api/cache/clear")
def clear_cache(user: Identity = Depends(admin_user)):
    if db_manager and hasattr(db_manager, "clear_cache"):
        db_manager.clear_cache("query:*")
    return {"status": "cleared"}


@app.get("/api/outliers/metrics")
def outliers_metrics(user: Identity = Depends(admin_user)):
    from shared.southern_baseline_api import SouthernBaselineAPI
    return SouthernBaselineAPI(db_manager).get_metrics()


@app.post("/api/outliers/refresh-cache")
def outliers_refresh(user: Identity = Depends(admin_user)):
    from shared.southern_baseline_api import SouthernBaselineAPI
    return SouthernBaselineAPI(db_manager).refresh_cache()


_MAX_BODY = 64 * 1024


async def _calibration(request: Request, user: Identity, handler):
    if calibration is None:
        raise HTTPException(status_code=404, detail="Not found")
    if "application/json" not in (request.headers.get("content-type") or ""):
        raise HTTPException(status_code=415, detail="Content-Type must be application/json")
    raw = await request.body()
    if len(raw) > _MAX_BODY:
        raise HTTPException(status_code=413, detail="Request body too large")
    from starlette.concurrency import run_in_threadpool
    result = await run_in_threadpool(handler, _event(request.url.path, user=user, body=raw.decode("utf-8") or "{}",
                                                     method="POST"), None)
    return _respond(result)


@app.post("/api/calibration/preview")
async def calibration_preview(request: Request, user: Identity = Depends(admin_user)):
    return await _calibration(request, user, calibration.lambda_handler_preview if calibration else None)


@app.post("/api/calibration/suggest")
async def calibration_suggest(request: Request, user: Identity = Depends(admin_user)):
    return await _calibration(request, user, calibration.lambda_handler_suggest if calibration else None)


@app.post("/api/calibration/commit")
async def calibration_commit(request: Request, user: Identity = Depends(admin_user)):
    return await _calibration(request, user, calibration.lambda_handler_commit if calibration else None)


@app.post("/api/calibration/revert")
async def calibration_revert(request: Request, user: Identity = Depends(admin_user)):
    return await _calibration(request, user, calibration.lambda_handler_revert if calibration else None)


@app.post("/api/calibration/history")
async def calibration_history(request: Request, user: Identity = Depends(admin_user)):
    return await _calibration(request, user, calibration.lambda_handler_history if calibration else None)
