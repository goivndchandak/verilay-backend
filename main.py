"""
Verilay — Main Application
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.responses import Response as StarletteResponse

from database import create_tables

from routers import auth, feed, cards, radar, shield, profile, search, notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n🚀 Verilay API starting up...")
    await create_tables()
    print("✅ Database tables ready\n")
    yield
    print("\n👋 Verilay API shutting down...\n")


app = FastAPI(
    title="Verilay API",
    description="The Layer of Truth the Internet Needs.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(feed.router)
app.include_router(cards.router)
app.include_router(radar.router)
app.include_router(shield.router)
app.include_router(profile.router)
app.include_router(search.router)
app.include_router(notifications.router)


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "app": "Verilay API", "version": "1.0.0"}


@app.get("/api", tags=["Health"])
async def api_info():
    return {
        "status": "ok",
        "endpoints": {
            "auth": "/api/auth",
            "feed": "/api/feed",
            "cards": "/api/cards",
            "radar": "/api/radar",
            "shield": "/api/shield",
            "users": "/api/users",
            "search": "/api/search",
            "notifications": "/api/notifications",
        },
    }


# ── Raw ASGI CORS — handles OPTIONS before anything else ──
_inner = app

class CORSWrapper:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS":
            response = StarletteResponse(
                content="OK",
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Max-Age": "86400",
                },
            )
            await response(scope, receive, send)
            return

        async def send_with_cors(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"access-control-allow-origin", b"*"))
                headers.append((b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS, PATCH"))
                headers.append((b"access-control-allow-headers", b"*"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_cors)

app = CORSWrapper(_inner)
