import logging
import uuid
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel

from app import auth, db, s3

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","service":"api","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)

REQUESTS_TOTAL = Counter("api_requests_total", "Total API requests", ["method", "endpoint", "status"])

app = FastAPI(title="API Service")


class UploadRequest(BaseModel):
    name: str
    type: str
    size: int


@app.on_event("startup")
def startup():
    db.check_db()
    s3.ensure_buckets()


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


@app.post("/api/img")
def post_img(body: UploadRequest, authorization: str | None = Header(default=None)):
    try:
        user_id = auth.verify_token(authorization)
    except ValueError as e:
        logger.warning("Auth failed: %s", e)
        REQUESTS_TOTAL.labels("POST", "/api/img", "400").inc()
        raise HTTPException(status_code=400, detail=str(e))

    if not body.type.startswith("image/"):
        REQUESTS_TOTAL.labels("POST", "/api/img", "400").inc()
        raise HTTPException(status_code=400, detail="Invalid mime type")

    if body.size > 10 * 1024 * 1024:
        REQUESTS_TOTAL.labels("POST", "/api/img", "400").inc()
        raise HTTPException(status_code=400, detail="File size exceeds 10MB")

    if len(body.name.encode("utf-8")) > 255:
        REQUESTS_TOTAL.labels("POST", "/api/img", "400").inc()
        raise HTTPException(status_code=400, detail="Filename too long")

    image_id = str(uuid.uuid4())

    try:
        endpoint = s3.get_presigned_upload_url(image_id)
    except Exception as e:
        logger.error("S3 presigned URL error: %s", e)
        REQUESTS_TOTAL.labels("POST", "/api/img", "500").inc()
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")

    try:
        db.insert_image(image_id, user_id, body.name, body.type, body.size)
    except Exception as e:
        logger.error("DB insert error: %s", e)
        REQUESTS_TOTAL.labels("POST", "/api/img", "500").inc()
        raise HTTPException(status_code=500, detail="Failed to save image metadata")

    REQUESTS_TOTAL.labels("POST", "/api/img", "200").inc()
    return {
        "status": "ok",
        "data": {
            "object_id": image_id,
            "endpoint": endpoint,
        },
    }


@app.get("/api/img")
def get_img(
    id: str = Query(...),
    authorization: str | None = Header(default=None),
):
    try:
        user_id = auth.verify_token(authorization)
    except ValueError as e:
        logger.warning("Auth failed: %s", e)
        REQUESTS_TOTAL.labels("GET", "/api/img", "400").inc()
        raise HTTPException(status_code=400, detail=str(e))

    try:
        UUID(id)
    except ValueError:
        REQUESTS_TOTAL.labels("GET", "/api/img", "400").inc()
        raise HTTPException(status_code=400, detail="Invalid image id")

    try:
        image = db.get_image(id)
    except Exception as e:
        logger.error("DB query error: %s", e)
        REQUESTS_TOTAL.labels("GET", "/api/img", "500").inc()
        raise HTTPException(status_code=500, detail="Database error")

    if image is None:
        REQUESTS_TOTAL.labels("GET", "/api/img", "404").inc()
        raise HTTPException(status_code=404, detail="Image not found")

    if str(image["user_id"]) != user_id:
        REQUESTS_TOTAL.labels("GET", "/api/img", "403").inc()
        raise HTTPException(status_code=403, detail="Forbidden")

    if image["status"] != "ready":
        REQUESTS_TOTAL.labels("GET", "/api/img", "406").inc()
        raise HTTPException(status_code=406, detail="Image not ready")

    base = s3.S3_EXTERNAL_URL
    REQUESTS_TOTAL.labels("GET", "/api/img", "200").inc()
    return {
        "status": "ok",
        "data": {
            "original": f"{base}/original/{image['name']}",
            "large": f"{base}/large/{id}.jpeg",
            "medium": f"{base}/medium/{id}.jpeg",
            "small": f"{base}/small/{id}.jpeg",
        },
    }
