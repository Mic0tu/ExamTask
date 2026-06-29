import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from app import db, processor, s3

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"img","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)

WEBHOOK_TOTAL = Counter("img_webhook_total", "Total webhook requests", ["status"])

app = FastAPI(title="IMG Service")


@app.on_event("startup")
def startup():
    processor.start_worker()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.get("/health")
def health():
    db_ok = db.check_db()
    s3_ok = s3.check_s3()
    status = "ok" if db_ok and s3_ok else "degraded"
    code = 200 if db_ok and s3_ok else 503
    return JSONResponse(
        status_code=code,
        content={"status": status, "database": db_ok, "s3": s3_ok},
    )


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/img/process")
async def process_webhook(request: Request):
    try:
        event = await request.json()
    except Exception as e:
        logger.error("Invalid webhook payload: %s", e)
        WEBHOOK_TOTAL.labels("error").inc()
        return JSONResponse(status_code=400, content={"status": "error"})

    object_key = processor.extract_object_key(event)
    if not object_key:
        logger.warning("No object key in webhook event")
        WEBHOOK_TOTAL.labels("ignored").inc()
        return {"status": "ignored"}

    logger.info("Webhook received for object %s", object_key)
    processor.enqueue(object_key)
    WEBHOOK_TOTAL.labels("queued").inc()
    return {"status": "queued"}
