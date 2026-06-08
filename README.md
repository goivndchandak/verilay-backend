# 🛡️ Verilay Backend API

> **The Layer of Truth the Internet Needs**

Backend API for the Verilay truth verification platform, built with FastAPI + PostgreSQL.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 15+
- (Optional) Redis for caching

### 2. Setup

```bash
# Clone and enter directory
cd verilay-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env from template
cp .env.example .env
# Edit .env with your database URL and secrets
```

### 3. Create PostgreSQL Database

```sql
CREATE DATABASE verilay;
```

### 4. Run the Server

```bash
uvicorn main:app --reload --port 8000
```

### 5. Open API Docs

Visit: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📡 API Endpoints

| Group | Prefix | Endpoints |
|-------|--------|-----------|
| **Auth** | `/api/auth` | send-otp, verify-otp, register, me |
| **Feed** | `/api/feed` | following, trending |
| **Cards** | `/api/cards` | create, get, vouch, counter, share |
| **Radar** | `/api/radar` | scan, mentions, risk-score, respond, weekly-stats |
| **Shield** | `/api/shield` | response-card, denial-statement, takedown, export-pdf, alert |
| **Users** | `/api/users` | profile, update, truth-log, cards, follow/unfollow, stats |
| **Search** | `/api/search` | search users and claims |
| **Notifications** | `/api/notifications` | list, unread-count, mark read |

---

## 🏗️ Project Structure

```
verilay-backend/
├── main.py                  # FastAPI app entry
├── config.py                # Settings from .env
├── database.py              # Async SQLAlchemy setup
├── models/                  # ORM models (10 tables)
│   ├── user.py              # User, SocialAccount
│   ├── card.py              # TruthCard, NewsLink
│   ├── reaction.py          # Vouch/Counter
│   ├── mention.py           # Radar mentions
│   ├── follower.py          # Follow relationships
│   └── notification.py      # Bell notifications
├── schemas/                 # Pydantic v2 schemas
│   ├── auth.py              # OTP, JWT, registration
│   ├── card.py              # Card CRUD responses
│   ├── radar.py             # Radar, risk, mentions
│   └── user.py              # Profile, follow, search
├── services/                # Business logic
│   ├── otp_service.py       # Email OTP (in-memory)
│   ├── trust_engine.py      # Trust & vouch scoring
│   ├── news_scanner.py      # NewsData.io + GNews
│   └── risk_engine.py       # Risk calculation
├── routers/                 # API endpoints
│   ├── auth.py
│   ├── feed.py
│   ├── cards.py
│   ├── radar.py
│   ├── shield.py
│   ├── profile.py
│   ├── search.py
│   └── notifications.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔑 Authentication Flow

1. User sends email to `POST /api/auth/send-otp`
2. OTP is printed to console (dev mode) or sent via email
3. User verifies with `POST /api/auth/verify-otp`
4. If new user → registers with `POST /api/auth/register`
5. JWT token returned → use in `Authorization: Bearer <token>` header

---

## 📋 Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL |
| Auth | JWT (python-jose) |
| Validation | Pydantic v2 |
| News APIs | NewsData.io + GNews.io |

---

Built with ❤️ for Verilay
