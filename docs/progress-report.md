# AutoMind AI Platform — Complete Progress Report

**Date:** July 3, 2026  
**AWS Account:** 536573256337 (jay-admin-automindai)  
**Region:** ap-south-1 (Mumbai)  
**Tasks Completed:** 26/26 (100%)  
**GitHub:** https://github.com/jaygaikwad-devops/CP-automindai

---

## 1. Infrastructure (Deployed to AWS)

### CloudFormation Stacks — All `CREATE_COMPLETE`

| Stack | Resources | Key Outputs |
|-------|-----------|-------------|
| **AutoMind-Vpc** | VPC, 6 subnets (2 public, 2 private, 2 isolated), NAT Gateway, Internet Gateway, Flow Logs | `vpc-04e4a1797d8e2aa64` |
| **AutoMind-Storage** | 3 S3 buckets + CloudFront (OAC) | `automind-assets-*`, `automind-tour-scripts-*`, `automind-cdn-origin-*` |
| **AutoMind-Database** | RDS PostgreSQL 15.17, DynamoDB `automind_sessions`, ElastiCache Redis | RDS: `automind-postgres.cv0qeeaiq055.ap-south-1.rds.amazonaws.com` |
| **AutoMind-Queue** | SQS processing queue + DLQ | `automind-processing-queue`, `automind-dead-letter-queue` |
| **AutoMind-Lambda** | 6 Lambda functions | See below |
| **AutoMind-Auth** | Cognito User Pool + API Gateway WebSocket | User Pool: `ap-south-1_2jP4Eyhxh` |
| **AutoMind-Compute** | ECS Fargate + ALB | **LIVE** |

### Live Endpoints

| Service | Endpoint | Status |
|---------|----------|--------|
| **Backend API (ALB)** | `http://automind-api-alb-2046660663.ap-south-1.elb.amazonaws.com` | ✅ Running |
| **CloudFront CDN** | `https://d216tnm1kuc704.cloudfront.net` | ✅ Active |
| **WebSocket API** | `wss://5nq4jw9sub.execute-api.ap-south-1.amazonaws.com/prod` | ✅ Active |
| **Frontend (local)** | `http://localhost:3001` | ✅ Running |
| **Backend (local)** | `http://localhost:8001` | ✅ Running |

### Lambda Functions (Deployed)

| Function | Runtime | Timeout | Memory | Trigger |
|----------|---------|---------|--------|---------|
| `automind-image-analyzer` | Python 3.11 | 5 min | 512 MB | SQS (image_analysis) |
| `automind-pdf-extractor` | Python 3.11 | 10 min | 1024 MB | SQS (pdf_extraction) |
| `automind-tour-sequencer` | Python 3.11 | 10 min | 1024 MB | SQS (tour_sequencing) |
| `automind-kb-builder` | Python 3.11 | 10 min | 512 MB | SQS (kb_building) |
| `automind-lead-scorer` | Python 3.11 | 30 sec | 256 MB | Direct invocation |
| `automind-reconciliation` | Python 3.11 | 5 min | 256 MB | CloudWatch (every 5 min) |

### Cognito User Pool

| Setting | Value |
|---------|-------|
| Pool ID | `ap-south-1_2jP4Eyhxh` |
| Client ID | `64ssi8eceqntpoucg0lqeog0ah` |
| Sign-in | Phone number (OTP via custom auth challenge) |
| Custom attributes | `rera_id`, `role`, `city` |
| Lambda triggers | `define-auth-challenge`, `create-auth-challenge`, `verify-auth-challenge` |

### DynamoDB Table: `automind_sessions`

| Key | Pattern |
|-----|---------|
| PK | `SESSION#{session_id}` |
| SK | `META` or `EVENT#{timestamp}#{event_type}` |
| GSI1PK | `CP#{cp_id}` |
| GSI1SK | `SCORE#{inverted_score_zero_padded}#{created_at}` |
| TTL | 30 days |

---

## 2. Backend API (FastAPI)

### REST Endpoints (20 total)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check |
| `POST` | `/api/v1/auth/otp/request` | None | Send OTP (rate limited 5/15min) |
| `POST` | `/api/v1/auth/otp/verify` | None | Verify OTP → JWT (24h). Dev: OTP=`123456` |
| `POST` | `/api/v1/auth/register` | CP JWT | Register CP (name + RERA ID) |
| `POST` | `/api/v1/auth/session/anonymous` | None | Create buyer session |
| `GET` | `/api/v1/dashboard/stats` | CP JWT | Monthly stats (cached 60s) |
| `GET` | `/api/v1/dashboard/hot-leads` | CP JWT | Hot leads list (sorted, max 50) |
| `GET` | `/api/v1/dashboard/leads/{id}` | CP JWT | Lead detail + events |
| `WS` | `/api/v1/dashboard/ws` | CP JWT | Real-time hot lead push |
| `GET` | `/api/v1/projects` | CP JWT | Project list (multi-tenant) |
| `POST` | `/api/v1/projects/{id}/share-link` | CP JWT | Generate WhatsApp share link |
| `GET` | `/api/v1/projects/tour/{slug}/click` | None | Track link click |
| `GET` | `/api/v1/billing/packs` | None | Credit pack listing |
| `POST` | `/api/v1/billing/purchase` | CP JWT | Razorpay order creation |
| `POST` | `/api/v1/billing/webhook` | None | Razorpay payment webhook |
| `POST` | `/api/v1/admin/projects` | Admin JWT | Create project |
| `POST` | `/api/v1/admin/partnerships` | Admin JWT | Assign CP to project |
| `DELETE` | `/api/v1/admin/partnerships/{id}` | Admin JWT | Remove partnership |
| `POST` | `/api/v1/admin/projects/{id}/assets` | Admin JWT | Upload asset |
| `POST` | `/api/v1/admin/projects/{id}/process` | Admin JWT | Trigger pipeline |
| `POST` | `/api/v1/tours/{session_id}/events` | None | Record tour event |

### WebSocket Endpoint

| URL | Auth | Protocol |
|-----|------|----------|
| `WS /ws/tour/{session_id}?session_token=JWT` | Buyer JWT | Chat + scoring |

### Backend Project Structure

```
backend/
├── app/
│   ├── api/           # auth, admin, billing, dashboard, projects, tours, websocket, health
│   ├── core/          # config, database, security, validators, middleware, exceptions, logging
│   ├── models/        # SQLAlchemy ORM (10 tables)
│   ├── schemas/       # Pydantic Tour_Script models
│   └── services/      # dynamodb, redis, lead_engine, notifications, s3, asset_validation
├── alembic/           # Database migrations
├── tests/             # 183 tests (pytest + hypothesis)
├── requirements.txt
└── Dockerfile
```

---

## 3. Frontend (Next.js 14 + TypeScript + Tailwind)

### Pages

| Route | Description | Auth |
|-------|-------------|------|
| `/` | Auto-redirect (authenticated → dashboard, else → login) | No |
| `/login` | OTP login (phone → OTP → JWT) | No |
| `/register` | First-time CP registration (name + RERA) | JWT |
| `/dashboard` | Stats cards + hot leads table + real-time WebSocket | JWT |
| `/dashboard/leads/[leadId]` | Lead detail: signals + session timeline | JWT |
| `/projects` | Project grid + WhatsApp share link generation | JWT |
| `/billing` | Credit pack purchase via Razorpay | JWT |
| `/t/[linkId]` | Buyer tour viewer: rooms, Priya, chat, contact | No |
| `/admin` | Admin: Create projects | JWT |
| `/admin/partnerships` | Admin: Assign/remove CP ↔ Project | JWT |
| `/admin/assets` | Admin: Upload assets + trigger processing | JWT |

### Frontend Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── login/           # OTP auth flow
│   │   ├── register/        # CP profile completion
│   │   ├── dashboard/       # Stats, hot leads, lead detail
│   │   ├── projects/        # Project grid + share links
│   │   ├── billing/         # Credit packs + Razorpay
│   │   ├── admin/           # Internal admin dashboard
│   │   └── t/[linkId]/      # Buyer tour viewer
│   ├── components/
│   │   ├── AuthGuard.tsx    # JWT validation + redirect
│   │   ├── Sidebar.tsx      # Navigation sidebar
│   │   ├── PriyaAvatar.tsx  # SVG avatar with mouth animation
│   │   ├── ChatInterface.tsx # WebSocket streaming chat
│   │   └── ContactForm.tsx  # Visit booking form
│   ├── hooks/
│   │   └── useWebSocket.ts  # Dashboard real-time updates
│   ├── lib/
│   │   ├── api.ts           # Typed API client (all endpoints)
│   │   └── auth.ts          # Token helpers
│   └── types/
│       └── index.ts         # Shared TypeScript interfaces
├── .env.local
├── next.config.js
├── tailwind.config.ts
├── Dockerfile
└── package.json
```

### Key Components

| Component | Description |
|-----------|-------------|
| **PriyaAvatar** | SVG face, mouth animation (280ms), reduced-motion support, 30s timeout |
| **ChatInterface** | WebSocket streaming, token-by-token render, typing indicator |
| **ContactForm** | Visit booking modal, phone validation |
| **AuthGuard** | JWT decode + expiry check + redirect |
| **useWebSocket** | Auto-reconnect, ping/pong, hot lead push handler |

---

## 4. Workers (Lambda Pipeline)

### Processing Pipeline Flow

```
Asset Upload → SQS → image_analyzer (Rekognition)
                   → pdf_extractor (Textract + Bedrock)
                        ↓ (both complete)
                   → tour_sequencer (Bedrock Claude → Tour_Script JSON)
                        ↓
                   → kb_builder (Bedrock Knowledge Base ingestion)
                        ↓
                   Project status → "tour_ready"
```

### Worker Files

```
workers/
├── image_analyzer/handler.py    # Rekognition DetectLabels
├── pdf_extractor/handler.py     # Textract + Bedrock structuring
├── tour_sequencer/handler.py    # Bedrock Claude → Tour_Script JSON
├── kb_builder/handler.py        # Bedrock KB data source + ingestion
├── orchestrator/handler.py      # Pipeline step dispatcher
├── lead_scorer/handler.py       # Non-chat event scoring (Lambda)
├── reconciliation/handler.py    # DynamoDB → RDS sync (every 5 min)
└── tests/ (18 tests)
```

---

## 5. Lead Scoring Engine

### Signal Weights

| Signal | Points | Max |
|--------|--------|-----|
| `time_on_tour_3min_plus` | +2 | Once |
| `room_revisited` | +1 | 2 (distinct rooms) |
| `price_question_asked` | +2 | Once |
| `emi_question_asked` | +3 | Once |
| `rera_question_asked` | +1 | Once |
| `amenities_question_asked` | +1 | Once |
| `returned_within_24h` | +2 | Once |
| `whatsapp_share_clicked` | +1 | Once |
| `visit_booking_clicked` | +4 | Once |

### Classification

| Score | Classification |
|-------|----------------|
| 0–3 | `browsing` |
| 4–6 | `warm` |
| 7–9 | `hot` → **CP Alert triggered** |
| visit_booking_clicked | `visit_booked` |

### Alert Flow

```
Score ≥ 7 → check_and_alert() → Gupshup WhatsApp → retry → SNS SMS fallback
                              → push_hot_lead_update() → CP dashboard WebSocket
```

---

## 6. Billing System

### Credit Packs

| Pack | Price | Credits | Per Credit |
|------|-------|---------|-----------|
| Starter | ₹999 | 2 | ₹500 |
| Growth | ₹3,999 | 10 | ₹400 |
| Agency | ₹14,999 | 50 | ₹300 |

### Flow

```
CP selects pack → Razorpay order created → Checkout → payment.captured webhook
→ Verify signature → Atomically add credits → Record transaction
```

---

## 7. DevOps & Deployment

### Docker

| File | Purpose |
|------|---------|
| `backend/Dockerfile` | Python 3.12-slim, health check, 2 uvicorn workers |
| `frontend/Dockerfile` | Multi-stage Node.js build, standalone output |
| `docker-compose.yml` | Full local stack (Postgres + Redis + Backend + Frontend) |

### Deployment Script

```bash
./scripts/deploy.sh all       # Full: CDK → migrations → ECR → ECS → CloudFront
./scripts/deploy.sh infra     # CDK stacks only
./scripts/deploy.sh backend   # Build + push image + ECS force-deploy
./scripts/deploy.sh frontend  # Build + S3 sync + CloudFront invalidation
./scripts/deploy.sh migrate   # Run Alembic migrations
```

### CI/CD

| Item | Value |
|------|-------|
| GitHub Repo | `jaygaikwad-devops/CP-automindai` |
| Branch | `main` |
| ECR Backend | `536573256337.dkr.ecr.ap-south-1.amazonaws.com/automind-api` |
| ECR Frontend | `536573256337.dkr.ecr.ap-south-1.amazonaws.com/automind-frontend` |

---

## 8. Test Coverage

| Module | Tests | Framework |
|--------|-------|-----------|
| Backend (FastAPI) | 183 | pytest + hypothesis + httpx |
| Workers (Lambda) | 18 | pytest + moto |
| Infrastructure (CDK) | 37 | jest + CDK assertions |
| **Total** | **238** | — |

### Property-Based Tests (Hypothesis)

| ID | Property | Validates |
|----|----------|-----------|
| P1 | Phone validation: 10 digits starting 6-9 | Req 1.1, 1.8, 5.4 |
| P2 | RERA validation: `RERA/{state}/{year}/{number}` | Req 1.5 |
| P3 | Lead score: sum of weights, capped at 10 | Req 9.1, 9.2 |
| P4 | Classification: correct tier per thresholds | Req 9.4 |
| P6 | Multi-tenant isolation: 403 for unassigned | Req 12.1, 12.2 |
| P9 | Tour Script round-trip serialization | Req 15.3 |
| P10 | Validation errors include path + constraint | Req 15.4 |
| P11 | Unknown fields ignored silently | Req 15.5 |
| P12 | Question classification: correct signal | Req 8.3–8.6 |
| P13 | Message length: 1-500 accepted | Req 8.8 |
| P14 | Alert threshold: one alert per session | Req 10.6 |
| P17 | Room revisit detection | Req 6.5 |
| P19 | Asset upload validation | Req 17.1–17.8 |
| P20 | Processing eligibility | Req 17.9 |
| P21 | Upload blocked by status | Req 17.12 |
| P22 | Admin-only auth | Req 16.5 |
| P23 | Access revocation immediacy | Req 16.4 |
| P24 | Duplicate partnership rejection | Req 16.7 |
| P26 | Pipeline sequencing constraint | Req 11.4 |

---

## 9. CORS Configuration

```python
cors_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://d216tnm1kuc704.cloudfront.net",
    "http://automind-api-alb-2046660663.ap-south-1.elb.amazonaws.com",
]
```

---

## 10. Database (PostgreSQL — 10 tables)

| Table | Purpose |
|-------|---------|
| `cps` | Channel Partners (phone, name, rera_id, credit_balance) |
| `builders` | Real estate developers |
| `projects` | Builder projects (tour_status, kb_id) |
| `partnerships` | CP ↔ Project assignments (multi-tenant isolation) |
| `share_links` | WhatsApp share links (url_slug, OG card, click_count) |
| `project_assets` | Uploaded files (images, videos, PDFs, floor plans) |
| `processing_jobs` | Pipeline job tracking (status, retry_count) |
| `subscriptions` | Razorpay billing (plan, period, grace) |
| `leads` | Materialized from DynamoDB for dashboard queries |
| `admins` | Internal admin users |
| `credit_transactions` | Credit purchase/deduction history |

---

## 11. Redis Cache

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `session:{session_id}` | 24h | Score + classification cache |
| `tour:{project_id}` | 1h | Tour script JSON cache |
| `dashboard:{cp_id}:{month}` | 60s | Dashboard stats cache |
| `otp_rate:{phone}` | 900s | OTP rate limiting (max 5) |
| `otp_attempts:{phone}` | 900s | Failed OTP counter (lock at 3) |

---

## 12. Running Locally

```bash
# Option 1: Docker Compose (full stack)
docker-compose up

# Option 2: Manual
cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001
cd frontend && npm run dev -- -p 3001

# Login: any phone + OTP 123456
```

---

## 13. Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│  CP Dashboard (Next.js)          Buyer Tour Viewer (Next.js)        │
│  localhost:3001                   /t/[linkId]                        │
└─────────────────┬──────────────────────────────┬────────────────────┘
                  │ REST + WebSocket              │ WebSocket
┌─────────────────▼──────────────────────────────▼────────────────────┐
│                      API LAYER (ECS Fargate)                         │
│  FastAPI (Python 3.12)                                               │
│  ALB: automind-api-alb-2046660663.ap-south-1.elb.amazonaws.com      │
│  ┌──────────┬───────────┬──────────┬──────────┬─────────────┐      │
│  │ Auth API │ Dashboard │ Projects │ Billing  │ WebSocket   │      │
│  │ (Cognito)│ (stats)   │ (share)  │(Razorpay)│ (chat+score)│      │
│  └──────────┴───────────┴──────────┴──────────┴─────────────┘      │
└────────┬───────────┬──────────┬──────────┬──────────────────────────┘
         │           │          │          │
┌────────▼───┐ ┌─────▼────┐ ┌──▼───┐ ┌────▼─────┐
│ PostgreSQL │ │ DynamoDB  │ │Redis │ │   SQS    │
│  (RDS)     │ │(sessions) │ │(cache)│ │(pipeline)│
└────────────┘ └───────────┘ └──────┘ └────┬─────┘
                                            │
┌───────────────────────────────────────────▼─────────────────────────┐
│                    LAMBDA WORKERS                                     │
│  image_analyzer → pdf_extractor → tour_sequencer → kb_builder       │
│  lead_scorer (non-chat events)                                       │
│  reconciliation (DynamoDB → RDS sync, every 5 min)                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 14. What Was Completed (All 26 Tasks)

| Week | Tasks | Description | Status |
|------|-------|-------------|--------|
| 1 | 1–4 | Infrastructure + Auth (CDK, Cognito, FastAPI, DB) | ✅ |
| 2 | 5–8 | AI Pipeline (admin, assets, Lambda workers) | ✅ |
| 3 | 9–14 | Lead Engine + WebSocket (scoring, chat, reconciliation) | ✅ |
| 4 | 15–19 | Notifications, dashboard, projects, billing | ✅ |
| 4 | 20 | Frontend: CP dashboard + auth | ✅ |
| 4 | 21 | Frontend: Buyer tour experience | ✅ |
| 4 | 22–23 | Frontend: Admin dashboard | ✅ |
| 4 | 25–26 | Integration wiring + deployment | ✅ |

---

*Generated: July 3, 2026*
