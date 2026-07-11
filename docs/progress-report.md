# AutoMind CP Portal — Final Progress Report

**Date:** July 11, 2026  
**AWS Account:** 536573256337 (jay-admin-automindai)  
**Region:** ap-south-1 (Mumbai)  
**GitHub:** https://github.com/jaygaikwad-devops/CP-automindai  
**Status:** ✅ DEPLOYED & LIVE

---

## 🌐 LIVE PRODUCTION URLs

| Service | URL | Status |
|---------|-----|--------|
| **Frontend (CloudFront)** | https://d216tnm1kuc704.cloudfront.net | ✅ Live |
| **Frontend (Custom Domain)** | https://app.automindai.info | ✅ (DNS propagating via GoDaddy) |
| **Backend API (HTTPS)** | https://api.automindai.info | ✅ Live |
| **Backend Health** | https://api.automindai.info/health | ✅ `{"status":"ok"}` |
| **Swagger Docs** | https://api.automindai.info/docs | ✅ Interactive API docs |

### How to Use

1. Open https://d216tnm1kuc704.cloudfront.net/login/
2. Enter phone: `8482861955` (or any 10-digit number starting with 6-9)
3. Click "Send OTP" (may show error — ignore it, OTP is auto-generated in dev mode)
4. Enter OTP: **`123456`**
5. You'll be redirected to the Dashboard
6. Navigate to Projects → see "Lodha Crown" and "Lodha Palava City"
7. Click "Share on WhatsApp" → generates a unique tour link

---

## 📊 Platform Overview

### What This Platform Does

AutoMind is a SaaS platform for real estate Channel Partners (CPs/brokers):
- CPs login via OTP → see their dashboard with hot leads
- CPs share AI virtual tour links via WhatsApp to buyers
- Buyers view tours narrated by "Priya" (AI avatar) → ask questions via chat
- Buyer engagement is scored in real-time (0-10)
- When score hits 7+ → CP gets instant WhatsApp alert + dashboard push
- CPs can purchase credit packs to generate tours for new projects

---

## 🏗️ Infrastructure (All deployed to AWS)

### CloudFormation Stacks — All `CREATE_COMPLETE`

| Stack | Key Resources |
|-------|---------------|
| **AutoMind-Vpc** | VPC, 6 subnets, NAT Gateway, Internet Gateway |
| **AutoMind-Storage** | 3 S3 buckets, CloudFront CDN (OAC) |
| **AutoMind-Database** | RDS PostgreSQL, DynamoDB, ElastiCache Redis |
| **AutoMind-Queue** | SQS processing queue + Dead Letter Queue |
| **AutoMind-Lambda** | 6 Lambda functions (AI pipeline + scoring) |
| **AutoMind-Auth** | Cognito User Pool + API Gateway WebSocket |
| **AutoMind-Compute** | ECS Fargate + ALB (HTTPS + host routing) |

### Network & Security

| Component | Details |
|-----------|---------|
| VPC | `vpc-04e4a1797d8e2aa64` (6 subnets, 3 AZs) |
| ALB | `automind-api-alb-2046660663.ap-south-1.elb.amazonaws.com` |
| HTTPS | ACM cert on ALB (TLS 1.3) + ACM cert on CloudFront |
| HTTP → HTTPS | 301 redirect on port 80 |
| CORS | `app.automindai.info`, `d216tnm1kuc704.cloudfront.net`, `localhost:3001` |

### DNS (GoDaddy + Route 53)

| Record | Type | Points To |
|--------|------|-----------|
| `api.automindai.info` | CNAME | ALB (backend) |
| `app.automindai.info` | CNAME | `d216tnm1kuc704.cloudfront.net` (frontend) |

### Databases

| Service | Endpoint |
|---------|----------|
| RDS PostgreSQL | `automind-postgres.cv0qeeaiq055.ap-south-1.rds.amazonaws.com:5432` |
| ElastiCache Redis | `automind-redis.a59iqn.0001.aps1.cache.amazonaws.com:6379` |
| DynamoDB | `automind_sessions` (GSI: CP hot leads by score) |
| Database Name | `cp_portal` (11 tables, 2 Alembic migrations applied) |

### ECS Fargate

| Setting | Value |
|---------|-------|
| Cluster | `automind-cluster` |
| Service | `automind-api` |
| Task Definition | `automind-api:7` |
| Image | `536573256337.dkr.ecr.ap-south-1.amazonaws.com/automind-api:v7` |
| CPU/Memory | 512 / 1024 MB |
| Auto-scaling | Min 1, Max 4 (CPU 70%, Memory 80%) |

### Lambda Functions

| Function | Trigger | Purpose |
|----------|---------|---------|
| `automind-image-analyzer` | SQS | Rekognition room tagging |
| `automind-pdf-extractor` | SQS | Textract + Bedrock PDF extraction |
| `automind-tour-sequencer` | SQS | Bedrock Claude → Tour Script |
| `automind-kb-builder` | SQS | Bedrock Knowledge Base ingestion |
| `automind-lead-scorer` | Direct | Non-chat event scoring |
| `automind-reconciliation` | CloudWatch 5min | DynamoDB → RDS sync |

---

## 🖥️ Backend API (20 REST + 2 WebSocket endpoints)

### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/otp/request` | Send OTP (dev: auto-succeeds) |
| POST | `/api/v1/auth/otp/verify` | Verify OTP → JWT. Dev OTP: `123456` |
| POST | `/api/v1/auth/register` | Register CP (name + RERA ID) |
| POST | `/api/v1/auth/session/anonymous` | Create buyer session |

### Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/dashboard/stats` | Monthly stats (tours, leads, conversions) |
| GET | `/api/v1/dashboard/hot-leads` | Hot leads sorted by score (max 50) |
| GET | `/api/v1/dashboard/leads/{id}` | Lead detail + signals + events |
| WS | `/api/v1/dashboard/ws` | Real-time hot lead push (< 3 seconds) |

### Projects & Tours

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/projects` | CP's assigned projects |
| POST | `/api/v1/projects/{id}/share-link` | Generate WhatsApp share link |
| GET | `/api/v1/projects/tour/{slug}/click` | Track link click |
| POST | `/api/v1/tours/{session_id}/events` | Record tour engagement event |
| WS | `/ws/tour/{session_id}` | Chat with Priya + live scoring |

### Billing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/billing/packs` | Credit packs (₹999/₹3,999/₹14,999) |
| POST | `/api/v1/billing/purchase` | Create Razorpay order |
| POST | `/api/v1/billing/webhook` | Razorpay payment confirmation |

### Admin

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/admin/projects` | Create project |
| POST | `/api/v1/admin/partnerships` | Assign CP to project |
| DELETE | `/api/v1/admin/partnerships/{id}` | Remove partnership |
| POST | `/api/v1/admin/projects/{id}/assets` | Upload asset |
| POST | `/api/v1/admin/projects/{id}/process` | Trigger AI pipeline |

---

## 🎨 Frontend (Next.js 14 — Static Export on CloudFront)

### Pages (12 routes)

| Route | Description |
|-------|-------------|
| `/login/` | OTP phone + verify flow |
| `/register/` | First-time CP registration |
| `/dashboard/` | Stats cards + hot leads table + real-time WebSocket |
| `/leads/?id=xxx` | Lead detail: score, signals, session timeline |
| `/projects/` | Project grid + WhatsApp share link generation |
| `/billing/` | Credit pack purchase (Razorpay checkout) |
| `/tour/?id=xxx` | Buyer tour viewer: rooms, Priya avatar, chat |
| `/admin/` | Admin: Create projects |
| `/admin/partnerships/` | Admin: Assign/remove CP ↔ Project |
| `/admin/assets/` | Admin: Upload assets + trigger processing |

### Key Components

| Component | Description |
|-----------|-------------|
| **PriyaAvatar** | SVG face with animated mouth (280ms, reduced-motion support) |
| **ChatInterface** | WebSocket streaming chat, token-by-token rendering |
| **ContactForm** | Visit booking with phone validation |
| **AuthGuard** | JWT decode + expiry check + redirect |
| **useWebSocket** | Auto-reconnect, ping/pong, hot lead push |

---

## 🧠 Lead Scoring Engine

### Signal Weights

| Signal | Points | Trigger |
|--------|--------|---------|
| `time_on_tour_3min_plus` | +2 | Viewing > 3 minutes |
| `room_revisited` | +1 (max 2) | Revisit a viewed room |
| `price_question_asked` | +2 | Chat about price/cost |
| `emi_question_asked` | +3 | Chat about EMI/loan |
| `rera_question_asked` | +1 | Chat about RERA |
| `amenities_question_asked` | +1 | Chat about amenities |
| `returned_within_24h` | +2 | Return visit |
| `whatsapp_share_clicked` | +1 | Buyer shares tour |
| `visit_booking_clicked` | +4 | Books a visit |

### Alert Flow (Score ≥ 7)

```
Buyer engagement → Score ≥ 7 → check_and_alert()
  → WhatsApp via Gupshup (retry once after 5s)
  → SMS via AWS SNS (fallback)
  → push_hot_lead_update() → CP dashboard WebSocket (< 3 seconds)
```

---

## 💰 Billing

| Pack | Price | Credits | Per Credit |
|------|-------|---------|-----------|
| Starter | ₹999 | 2 | ₹500 |
| Growth | ₹3,999 | 10 | ₹400 |
| Agency | ₹14,999 | 50 | ₹300 |

---

## 🗄️ Database Schema (11 tables)

`cps`, `builders`, `projects`, `partnerships`, `share_links`, `project_assets`, `processing_jobs`, `subscriptions`, `leads`, `admins`, `credit_transactions`

### Demo Data Seeded

| Entity | Data |
|--------|------|
| Builder | Lodha Group |
| Projects | Lodha Crown (Thane), Lodha Palava City (Dombivli) |
| CP | Jay Gaikwad (8482861955) with partnerships to both projects |

---

## 🧪 Test Coverage

| Module | Tests | Framework |
|--------|-------|-----------|
| Backend | 183 | pytest + hypothesis |
| Workers | 18 | pytest + moto |
| Infrastructure | 37 | jest + CDK assertions |
| **Total** | **238** | — |

---

## 🐳 DevOps

### Docker

- `backend/Dockerfile` — Python 3.12 + setuptools<81 + health check
- `frontend/Dockerfile` — Multi-stage Node.js build
- `docker-compose.yml` — Full local stack

### Deployment

```bash
./scripts/deploy.sh all       # Full deployment
./scripts/deploy.sh backend   # ECR push + ECS redeploy
./scripts/deploy.sh frontend  # S3 sync + CloudFront invalidation
```

### Git

```
4ffbe4c Frontend deployed to CloudFront - LIVE
c1de393 HTTPS + DNS routing on ALB
91fca9b Production deployment - ECS, SG rules, DB + migrations
303e2c3 Integration wiring, Docker support
c3476bb Buyer tour experience + admin dashboard
b0bd225 Next.js CP dashboard frontend
```

---

## ⚠️ Known Issues & Remaining Items

| Issue | Impact | Fix |
|-------|--------|-----|
| `/otp/request` fails (Redis timeout in ECS) | "Send OTP" button shows error | OTP still works — just enter `123456` directly |
| `app.automindai.info` DNS propagation | GoDaddy CNAME updated, propagating | Wait 1 hour or use CloudFront URL directly |
| Bedrock KB not connected | Chat returns placeholder responses | Need to ingest project data into Bedrock KB |
| Gupshup not configured | WhatsApp alerts don't send | Add `GUPSHUP_API_KEY` to ECS env |
| Razorpay not configured | Payment checkout won't open | Add `RAZORPAY_KEY_ID` to ECS env |

### To Fix OTP Request (Redis):
Add Redis security group rule for port 6379 from ECS (already done — may need ECS service restart).

### To Enable Real WhatsApp Alerts:
```bash
# Add to ECS task definition environment:
GUPSHUP_API_KEY=<your-key>
GUPSHUP_APP_NAME=AutoMindAI
GUPSHUP_SOURCE_NUMBER=<registered-number>
```

### To Enable Payments:
```bash
RAZORPAY_KEY_ID=<your-live-key>
RAZORPAY_KEY_SECRET=<your-live-secret>
RAZORPAY_WEBHOOK_SECRET=<webhook-secret>
```

---

## 📐 Architecture

```
 Browser (CP/Buyer)
       │
       ▼
 CloudFront (d216tnm1kuc704.cloudfront.net)
 ├── Static frontend (S3)
 └── URL rewrite function (directory → index.html)
       │
       │  API calls (CORS)
       ▼
 ALB (api.automindai.info) — HTTPS 443
       │
       ▼
 ECS Fargate (automind-api:v7)
 ├── FastAPI (20 REST + 2 WebSocket endpoints)
 ├── JWT auth (HS256, 24h expiry)
 ├── Dev OTP bypass (123456)
 └── Inline lead scoring + dashboard push
       │
       ├── PostgreSQL (RDS) — 11 tables
       ├── DynamoDB — sessions + events
       ├── Redis — cache + rate limits
       ├── SQS → Lambda pipeline (4 workers)
       ├── Cognito — OTP auth
       ├── Bedrock — AI chat (placeholder)
       ├── Gupshup — WhatsApp alerts
       └── Razorpay — credit purchases
```

---

*Generated: July 11, 2026*
