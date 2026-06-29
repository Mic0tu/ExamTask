import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel

from app import db

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"push","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)

NOTIFY_TOTAL = Counter("push_notify_total", "Total notify requests", ["status"])

app = FastAPI(title="PUSH Service")


@app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


class NotifyRequest(BaseModel):
    object: str
    object_id: str
    user_id: str
    status: str


@app.get("/health")
def health():
    db_ok = db.check_db()
    code = 200 if db_ok else 503
    return JSONResponse(
        status_code=code,
        content={"status": "ok" if db_ok else "degraded", "database": db_ok},
    )


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/notify")
def notify(body: NotifyRequest):
    try:
        image = db.get_image(body.object_id)
    except Exception as e:
        logger.error("Database error: %s", e)
        NOTIFY_TOTAL.labels("error").inc()
        raise HTTPException(status_code=500, detail="Database error")

    if image is None:
        NOTIFY_TOTAL.labels("not_found").inc()
        raise HTTPException(status_code=404, detail="Image not found")

    log_entry = {
        "log": "notify",
        "user_id": body.user_id,
        "object": body.object,
        "object_id": body.object_id,
        "filename": image["name"],
        "size": image["original_size"],
        "status": body.status,
    }
    logger.info(json.dumps(log_entry))
    NOTIFY_TOTAL.labels("ok").inc()
    return {"status": "ok"}
