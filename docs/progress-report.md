# AutoMind AI Platform — Complete Progress Report

**Date:** July 9, 2026  
**AWS Account:** 536573256337 (jay-admin-automindai)  
**Region:** ap-south-1 (Mumbai)  
**Tasks Completed:** 27/27 (100%)  
**GitHub:** https://github.com/jaygaikwad-devops/CP-automindai

---

## LIVE PRODUCTION ENDPOINTS

| Service | URL | Status |
|---------|-----|--------|
| **Backend API (HTTPS)** | `https://api.automindai.info` | ✅ Live |
| **Backend Health Check** | `https://api.automindai.info/health` | ✅ `{"status":"ok"}` |
| **Frontend App** | `https://app.automindai.info` | 🟡 Target group ready, awaiting container |
| **HTTP → HTTPS Redirect** | `http://api.automindai.info` | ✅ 301 → HTTPS |
| **CloudFront CDN** | `https://d216tnm1kuc704.cloudfront.net` | ✅ Active |
| **WebSocket API** | `wss://5nq4jw9sub.execute-api.ap-south-1.amazonaws.com/prod` | ✅ Active |
| **Local Frontend** | `http://localhost:3001` | ✅ Running |
| **Local Backend** | `http://localhost:8001` | ✅ Running |

### Quick Test Commands

```bash
# Health check
curl https://api.automindai.info/health

# Login (dev mode, OTP = 123456 for any phone)
curl -X POST https://api.automindai.info/api/v1/auth/otp/verify \
  -H "Content-Type: application/json" \
  -d '{"phone":"9876543210","otp":"123456"}'

# Get credit packs (no auth needed)
curl https://api.automindai.info/api/v1/billing/packs
```

---

## 1. Infrastructure (Deployed to AWS)

### CloudFormation Stacks — All `CREATE_COMPLETE`

| Stack | Resources | Key Outputs |
|-------|-----------|-------------|
| **AutoMind-Vpc** | VPC, 6 subnets (2 public, 2 private, 2 isolated), NAT Gateway, IGW, Flow Logs | `vpc-04e4a1797d8e2aa64` |
| **AutoMind-Storage** | 3 S3 buckets + CloudFront (OAC) | `d216tnm1kuc704.cloudfront.net` |
| **AutoMind-Database** | RDS PostgreSQL 15.17, DynamoDB `automind_sessions`, ElastiCache Redis | See below |
| **AutoMind-Queue** | SQS processing queue + DLQ | `automind-processing-queue` |
| **AutoMind-Lambda** | 6 Lambda functions | See below |
| **AutoMind-Auth** | Cognito User Pool + API Gateway WebSocket | Pool: `ap-south-1_2jP4Eyhxh` |
| **AutoMind-Compute** | ECS Fargate + ALB + HTTPS | **LIVE** |

### ALB Configuration (HTTPS + DNS Routing)

| Listener | Port | Action |
|----------|------|--------|
| **HTTPS** | 443 | ACM cert `b312c7a2-...`, TLS 1.3 |
| → Host: `app.automindai.info` | | Forward → `automind-frontend-tg` (port 3000) |
| → Default (api.automindai.info) | | Forward → `automind-api-tg` (port 8000) |
| **HTTP** | 80 | Redirect 301 → HTTPS 443 |

### Security Groups

| SG | Allows |
|----|--------|
| `sg-023c232cba5f4a5fe` (ALB) | Inbound: 80/tcp, 443/tcp from 0.0.0.0/0 |
| `sg-0d76ea23c02f7155c` (ECS Service) | Inbound: 8000/tcp from ALB SG |
| `sg-08424c3762bcec8bc` (RDS) | Inbound: 5432/tcp from ECS Service SG |
| `sg-077301b78afdf71bb` (Redis) | Inbound: 6379/tcp from ECS Service SG |

### Database Endpoints

| Service | Endpoint |
|---------|----------|
| RDS PostgreSQL | `automind-postgres.cv0qeeaiq055.ap-south-1.rds.amazonaws.com:5432` |
| ElastiCache Redis | `automind-redis.a59iqn.0001.aps1.cache.amazonaws.com:6379` |
| DynamoDB Table | `automind_sessions` (GSI: CP#{cp_id} / SCORE#{...}) |

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

### ECR Repositories

| Repository | Latest Image |
|------------|-------------|
| `automind-api` | `v7` (Python 3.12 + FastAPI + setuptools<81) |
| `automind-frontend` | Created, awaiting push |

---

## 2. Backend API (FastAPI — 20 Endpoints)

### REST Endpoints

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

### WebSocket Endpoints

| URL | Auth | Protocol |
|-----|------|----------|
| `WS /ws/tour/{session_id}?session_token=JWT` | Buyer JWT | Chat + scoring |
| `WS /api/v1/dashboard/ws` | CP JWT | Real-time hot lead push |

### Backend Project Structure

```
backend/
├── app/
│   ├── api/           # auth, admin, billing, dashboard, projects, tours, websocket, health
│   ├── core/          # config, database, security, validators, middleware, exceptions, logging
│   ├── models/        # SQLAlchemy ORM (11 tables)
│   ├── schemas/       # Pydantic Tour_Script models
│   └── services/      # dynamodb, redis, lead_engine, notifications, s3, asset_validation
├── alembic/           # Database migrations (2 revisions applied)
├── tests/             # 183 tests (pytest + hypothesis)
├── requirements.txt
└── Dockerfile
```

---

## 3. Frontend (Next.js 14 + TypeScript + Tailwind)

### Pages (11 routes)

| Route | Description | Auth |
|-------|-------------|------|
| `/` | Auto-redirect (authenticated → dashboard, else → login) | No |
| `/login` | OTP login (phone → OTP → JWT) | No |
| `/register` | First-time CP registration (name + RERA) | JWT |
| `/dashboard` | Stats cards + hot leads table + real-time WebSocket | JWT |
| `/dashboard/leads/[leadId]` | Lead detail: signals + session timeline | JWT |
| `/projects` | Project grid + WhatsApp share link generation | JWT |
| `/billing` | Credit pack purchase via Razorpay | JWT |
| `/t/[linkId]` | Buyer tour viewer: rooms, Priya avatar, chat, contact form | No |
| `/admin` | Admin: Create projects | JWT |
| `/admin/partnerships` | Admin: Assign/remove CP ↔ Project | JWT |
| `/admin/assets` | Admin: Upload assets + trigger processing | JWT |

### Key Components

| Component | Description |
|-----------|-------------|
| **PriyaAvatar** | SVG face, mouth animation (280ms cycle), reduced-motion support, 30s timeout |
| **ChatInterface** | WebSocket streaming, token-by-token render, typing indicator |
| **ContactForm** | Visit booking modal, phone validation |
| **AuthGuard** | JWT decode + expiry check + redirect |
| **Sidebar** | Navigation with active state |
| **useWebSocket** | Auto-reconnect, ping/pong, hot lead push handler |

---

## 4. Workers (Lambda Pipeline)

### Processing Pipeline

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

### Alert Flow (Score ≥ 7)

```
check_and_alert() → Gupshup WhatsApp → retry 5s → SNS SMS fallback
                  → push_hot_lead_update() → CP dashboard WebSocket (< 3s)
```

---

## 6. Billing System

| Pack | Price | Credits |
|------|-------|---------|
| Starter | ₹999 | 2 |
| Growth | ₹3,999 | 10 |
| Agency | ₹14,999 | 50 |

---

## 7. Database Schema (PostgreSQL — 11 tables)

| Table | Purpose |
|-------|---------|
| `cps` | Channel Partners (phone, name, rera_id, credit_balance) |
| `builders` | Real estate developers |
| `projects` | Builder projects (tour_status, kb_id, hero_image_url) |
| `partnerships` | CP ↔ Project assignments (multi-tenant isolation) |
| `share_links` | WhatsApp share links (url_slug, OG card, click_count) |
| `project_assets` | Uploaded files (images, videos, PDFs, floor plans) |
| `processing_jobs` | Pipeline job tracking (status, retry_count) |
| `subscriptions` | Razorpay billing (plan, period, grace) |
| `leads` | Materialized from DynamoDB for dashboard queries |
| `admins` | Internal admin users |
| `credit_transactions` | Credit purchase/deduction history |

---

## 8. Test Coverage

| Module | Tests | Framework |
|--------|-------|-----------|
| Backend (FastAPI) | 183 | pytest + hypothesis + httpx |
| Workers (Lambda) | 18 | pytest + moto |
| Infrastructure (CDK) | 37 | jest + CDK assertions |
| **Total** | **238** | — |

---

## 9. DevOps & Deployment

### Docker

| File | Purpose |
|------|---------|
| `backend/Dockerfile` | Python 3.12-slim + setuptools<81, health check, 2 workers |
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

### Git History

```
c1de393 feat: HTTPS + DNS routing on ALB
91fca9b feat: Production deployment - ECS task def v6, SG rules, DB + migrations
5374e75 docs: Complete progress report
303e2c3 feat: Integration wiring, deployment pipeline, Docker support
c3476bb feat: Add buyer tour experience + admin dashboard
6598c52 docs: Add frontend routes documentation
b0bd225 feat: Add Next.js CP dashboard frontend with auth, dashboard, projects, billing
```

---

## 10. CORS Configuration

```python
cors_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://d216tnm1kuc704.cloudfront.net",
    "http://automind-api-alb-2046660663.ap-south-1.elb.amazonaws.com",
    "https://api.automindai.info",
    "https://app.automindai.info",
]
```

---

## 11. Remaining Items

| Item | Status | What's Needed |
|------|--------|---------------|
| Frontend container on ECS | 🟡 | Push `automind-frontend` Docker image, create ECS service registered to `automind-frontend-tg` |
| Seed demo data | 🟡 | Insert builder + project + partnership for demo |
| Real Cognito OTP | 🟡 | Set `COGNITO_USER_POOL_ID` + `COGNITO_CLIENT_ID` env vars in ECS for production SMS |
| Gupshup WhatsApp | 🟡 | Add `GUPSHUP_API_KEY` env var for real WhatsApp alerts |
| Razorpay Live | 🟡 | Add `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET` for live payments |
| GitHub Actions CI/CD | 🟡 | Automate push → build → deploy |
| Bedrock KB Integration | 🟡 | Replace placeholder chat responses with real RAG |

### To deploy frontend:

```bash
cd frontend
docker build -t automind-frontend:latest .
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin 536573256337.dkr.ecr.ap-south-1.amazonaws.com
docker tag automind-frontend:latest 536573256337.dkr.ecr.ap-south-1.amazonaws.com/automind-frontend:latest
docker push 536573256337.dkr.ecr.ap-south-1.amazonaws.com/automind-frontend:latest
# Then create ECS task definition + service targeting automind-frontend-tg
```

---

## 12. Architecture Diagram

```
                    ┌─── https://app.automindai.info ───┐
                    │          (Next.js Frontend)        │
                    └───────────────┬────────────────────┘
                                    │
         ┌──────── ALB (HTTPS 443, ACM cert) ────────────┐
         │  Host: app.* → frontend-tg (port 3000)        │
         │  Default:    → backend-tg  (port 8000)        │
         │  HTTP 80:    → 301 redirect HTTPS              │
         └──────────────────────┬─────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  ECS Fargate Cluster   │
                    │  ┌─────────────────┐  │
                    │  │ automind-api:v7  │  │
                    │  │ FastAPI (8000)   │  │
                    │  └────────┬────────┘  │
                    └───────────┼───────────┘
                                │
         ┌──────────┬───────────┼───────────┬──────────┐
         │          │           │           │          │
    ┌────▼───┐ ┌────▼────┐ ┌───▼───┐ ┌─────▼────┐ ┌──▼──┐
    │  RDS   │ │DynamoDB │ │ Redis │ │   SQS    │ │ S3  │
    │Postgres│ │Sessions │ │ Cache │ │ Pipeline │ │Asset│
    └────────┘ └─────────┘ └───────┘ └─────┬────┘ └─────┘
                                            │
                    ┌───────────────────────▼───────────────┐
                    │          Lambda Workers               │
                    │  image_analyzer → pdf_extractor       │
                    │  → tour_sequencer → kb_builder        │
                    │  lead_scorer, reconciliation          │
                    └──────────────────────────────────────┘
```

---

*Generated: July 9, 2026*
