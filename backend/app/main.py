import base64
import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import settings
from app.services.visual_media import MEDIA_ROOT

app = FastAPI(title=settings.app_name)


def _authorized(header: str) -> bool:
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header.removeprefix("Basic ").strip()).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return False
    return secrets.compare_digest(username, settings.admin_username) and secrets.compare_digest(password, settings.admin_password)


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.admin_password or request.url.path == "/health":
            return await call_next(request)
        if request.url.path == "/api/owner-bot/telegram/webhook":
            return await call_next(request)
        if _authorized(request.headers.get("authorization", "")):
            return await call_next(request)
        return JSONResponse(
            {"detail": "Authentication required"},
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="ERA Media Factory"'},
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BasicAuthMiddleware)
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


app.include_router(api_router)


@app.on_event("startup")
def start_owner_bot() -> None:
    from app.api.routes.owner_bot import start_owner_bot_poller

    start_owner_bot_poller()
