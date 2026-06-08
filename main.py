"""
Verilay — Main Application
FastAPI app entry point with CORS, router registration, and startup tasks.

Run with:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import create_tables

# Import all routers
from routers import auth, feed, cards, radar, shield, profile, search, notifications


# ── Lifespan: startup / shutdown ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run tasks on startup and shutdown."""
    # ── Startup ──
    print("\n🚀 Verilay API starting up...")
    print("📦 Creating database tables...")
    await create_tables()
    print("✅ Database tables ready")
    print("🌐 API docs available at: http://localhost:8000/docs\n")
    yield
    # ── Shutdown ──
    print("\n👋 Verilay API shutting down...\n")


# ── Create FastAPI App ──
app = FastAPI(
    title="Verilay API",
    description=(
        "The Layer of Truth the Internet Needs. "
        "Backend API for the Verilay truth verification platform."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register Routers ──
app.include_router(auth.router)
app.include_router(feed.router)
app.include_router(cards.router)
app.include_router(radar.router)
app.include_router(shield.router)
app.include_router(profile.router)
app.include_router(search.router)
app.include_router(notifications.router)


# ── Health Check ──
@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": "Verilay API",
        "version": "1.0.0",
        "tagline": "The Layer of Truth the Internet Needs",
    }


@app.get("/api", tags=["Health"])
async def api_info():
    """API info endpoint."""
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
        "docs": "/docs",
        "redoc": "/redoc",
    }
