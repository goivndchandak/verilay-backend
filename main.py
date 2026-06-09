"""
Verilay — Main Application
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from database import create_tables

from routers import auth, feed, cards, radar, shield, profile, search, notifications


# ── Manual CORS fix for preflight OPTIONS ──
class CORSPreflight(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "*",
                    "Access-Control-Allow-Headers": "*",
                },
            )
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response


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

# Add BOTH middlewares — manual one catches OPTIONS, standard one handles rest
app.add_middleware(CORSPreflight)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
