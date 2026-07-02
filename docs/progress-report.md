# AutoMind AI Platform — Technical Progress Report

**Date:** July 1, 2026  
**AWS Account:** 536573256337 (jay-admin-automindai)  
**Region:** ap-south-1 (Mumbai)  
**Tasks Completed:** 1–14 of 26 (Week 1–3 of 4)

---

## 1. Infrastructure (Deployed to AWS)

### CloudFormation Stacks — All `CREATE_COMPLETE`

| Stack | Resources | Key Outputs |
|-------|-----------|-------------|
| **AutoMind-Vpc** | VPC, 6 subnets (2 public, 2 private, 2 isolated), NAT Gateway, Internet Gateway, Flow Logs | `vpc-04e4a1797d8e2aa64` |
| **AutoMind-Storage** | 3 S3 buckets + CloudFront (OAC) | `automind-assets-*`, `automind-tour-scripts-*`, `automind-cdn-origin-*` |
| **AutoMind-Database** | RDS PostgreSQL 15.17, DynamoDB `automind_sessions`, ElastiCache Redis | RDS: `automind-postgres.cv0qeeaiq055.ap-south-1.rds.amazonaws.com`, Redis: `automind-redis.a59iqn.0001.aps1.cache.amazonaws.com` |
| **AutoMind-Queue** | SQS processing queue + DLQ | `automind-processing-queue`, `automind-dead-letter-queue` |
| **AutoMind-Lambda** | 6 Lambda functions | See below |
| **AutoMind-Auth** | Cognito User Pool + API Gateway WebSocket | User Pool: `ap-south-1_2jP4Eyhxh`, WebSocket: `wss://5nq4jw9sub.execute-api.ap-south-1.amazonaws.com/prod` |
| **AutoMind-Compute** | ECS Fargate + ALB (code ready, awaiting container image) | Defined but not deployed yet |

### Lambda Functions (Deployed)

| Function | Runtime | Timeout | Memory | Trigger |
|----------|---------|---------|--------|---------|
| `automind-image-analyzer` | Python 3.11 | 5 min | 512 MB | SQS (image_analysis filter) |
| `automind-pdf-extractor` | Python 3.11 | 10 min | 1024 MB | SQS (pdf_extraction filter) |
| `automind-tour-sequencer` | Python 3.11 | 10 min | 1024 MB | SQS (tour_sequencing filter) |
| `automind-kb-builder` | Python 3.11 | 10 min | 512 MB | SQS (kb_building filter) |
| `automind-lead-scorer` | Python 3.11 | 30 sec | 256 MB | Direct invocation / API GW |
| `automind-reconciliation` | Python 3.11 | 5 min | 256 MB | CloudWatch Events (every 5 min) |

### Cognito User Pool

| Setting | Value |
|---------|-------|
| Pool ID | `ap-south-1_2jP4Eyhxh` |
| Client ID | `64ssi8eceqntpoucg0lqeog0ah` |
| Sign-in | Phone number (OTP via custom auth challenge) |
| Custom attributes | `rera_id`, `role`, `city` |
| Lambda triggers | `define-auth-challenge`, `create-auth-challenge`, `verify-auth-challenge` |

### WebSocket API Gateway

| Route | Description |
|-------|-------------|
| `$connect` | JWT session_token validation |
| `$disconnect` | Cleanup |
| `chat` | Priya RAG-powered Q&A |
| `room_navigate` | Room navigation events |
| **URL** | `wss://5nq4jw9sub.execute-api.ap-south-1.amazonaws.com/prod` |

### DynamoDB Table: `automind_sessions`

| Key | Pattern |
|-----|---------|
| PK | `SESSION#{session_id}` |
| SK | `META` or `EVENT#{timestamp}#{event_type}` |
| GSI1PK | `CP#{cp_id}` |
| GSI1SK | `SCORE#{inverted_score_zero_padded}#{created_at}` |
| TTL | 30 days |

### RDS PostgreSQL Schema (10 tables)

| Table | Purpose |
|-------|---------|
| `cps` | Channel Partners (phone, name, rera_id, subscription) |
| `builders` | Real estate developers |
| `projects` | Builder projects (tour_status, kb_id) |
| `partnerships` | CP ↔ Project assignments (multi-tenant isolation) |
| `share_links` | WhatsApp share links (url_slug, OG card) |
| `project_assets` | Uploaded files (images, videos, PDFs, floor plans) |
| `processing_jobs` | Pipeline job tracking (status, retry_count) |
| `subscriptions` | Razorpay billing (plan, period, grace) |
| `leads` | Materialized from DynamoDB for dashboard queries |
| `admins` | Internal admin users |

**Indexes:** `idx_partnerships_cp`, `idx_partnerships_project`, `idx_share_links_slug`, `idx_leads_cp_score`, `idx_leads_session`, `idx_project_assets_project`, `idx_projects_builder`

---

## 2. Backend API (FastAPI on Python 3.11)

### Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── health.py          # GET /health
│   │   ├── auth.py            # /api/v1/auth/*
│   │   ├── admin.py           # /api/v1/admin/*
│   │   ├── tours.py           # /api/v1/tours/*
│   │   └── websocket.py       # /ws/tour/{session_id}
│   ├── core/
│   │   ├── config.py          # Pydantic settings (env vars)
│   │   ├── database.py        # Async SQLAlchemy engine + session
│   │   ├── security.py        # JWT create/decode/get_current_user
│   │   ├── validators.py      # Phone + RERA validation
│   │   ├── tenant_isolation.py # Multi-tenant access control
│   │   ├── middleware.py      # Request ID middleware
│   │   ├── logging.py         # Structured JSON logging
│   │   └── exceptions.py      # Global exception handlers
│   ├── models/                 # SQLAlchemy ORM models (10 tables)
│   ├── schemas/
│   │   └── tour_script.py     # Pydantic Tour_Script models
│   └── services/
│       ├── dynamodb_session.py # DynamoDB session CRUD + GSI1 queries
│       ├── redis_cache.py      # Redis cache layer (score, tour, dashboard, OTP)
│       ├── lead_engine.py      # Score calculation + classification + alerts
│       ├── tour_script_service.py # Serialize/parse/validate Tour_Script
│       ├── asset_validation.py # Upload validation (format, size, count)
│       ├── s3_service.py       # S3 file upload
│       ├── rds_leads.py        # RDS leads upsert (dual-write target)
│       └── notifications.py    # Alert dispatch (placeholder)
├── alembic/                    # Database migrations
├── tests/                      # 183 tests
├── requirements.txt
└── Dockerfile
```

### REST Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check → `{"status": "ok"}` |
| `POST` | `/api/v1/auth/otp/request` | None | Send OTP to phone (rate limited 5/15min) |
| `POST` | `/api/v1/auth/otp/verify` | None | Verify OTP → JWT token (24h) |
| `POST` | `/api/v1/auth/register` | CP JWT | Register CP (name + RERA ID) |
| `POST` | `/api/v1/auth/session/anonymous` | None | Create buyer session → short JWT |
| `POST` | `/api/v1/admin/projects` | Admin JWT | Create project |
| `POST` | `/api/v1/admin/partnerships` | Admin JWT | Assign CP to project |
| `DELETE` | `/api/v1/admin/partnerships/{id}` | Admin JWT | Revoke CP access |
| `POST` | `/api/v1/admin/projects/{id}/assets` | Admin JWT | Upload asset (multipart) |
| `POST` | `/api/v1/admin/projects/{id}/process` | Admin JWT | Trigger AI pipeline |
| `POST` | `/api/v1/tours/{session_id}/events` | None | Record tour event → score update |

### WebSocket Endpoint

| URL | Auth | Description |
|-----|------|-------------|
| `WS /ws/tour/{session_id}?session_token=JWT` | Buyer JWT (query param) | Real-time chat + scoring |

**WebSocket Protocol:**

```
Client → Server:
  {"action": "chat", "message": "What is the price?"}
  {"action": "room_navigate", "room_index": 3}

Server → Client:
  {"type": "talking_start"}
  {"type": "chat_token", "token": "The", "sequence": 1}
  {"type": "chat_end", "full_response": "..."}
  {"type": "talking_end"}
  {"type": "score_update", "score": 7, "classification": "hot"}
  {"type": "ping"} (keepalive every 30s)
  {"type": "error", "code": "...", "message": "..."}
```

---

## 3. Workers (Lambda Pipeline)

### Processing Pipeline Flow

```
Asset Upload → SQS → image_analyzer (Rekognition)
                   → pdf_extractor (Textract + Bedrock)
                        ↓ (both complete)
                   → tour_sequencer (Bedrock Claude → tour-script.json)
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
├── requirements.txt
└── tests/ (18 tests)
```

---

## 4. Lead Scoring Engine

### Signal Weights

| Signal | Points | Trigger |
|--------|--------|---------|
| `time_on_tour_3min_plus` | +2 | Tour viewing > 3 min |
| `room_revisited` | +1 (max 2) | Revisit a previously viewed room |
| `price_question_asked` | +2 | Chat contains price/cost/rate |
| `emi_question_asked` | +3 | Chat contains EMI/loan/mortgage |
| `rera_question_asked` | +1 | Chat contains RERA/registration |
| `amenities_question_asked` | +1 | Chat contains amenities/gym/pool |
| `returned_within_24h` | +2 | Return visit within 24 hours |
| `whatsapp_share_clicked` | +1 | Buyer shares via WhatsApp |
| `visit_booking_clicked` | +4 | Buyer clicks visit booking |

### Classification

| Score Range | Classification |
|-------------|----------------|
| 0–3 | `browsing` |
| 4–6 | `warm` |
| 7–9 | `hot` |
| visit_booking_clicked = true | `visit_booked` (regardless of score) |

### Alert Threshold: Score ≥ 7 → WhatsApp alert to CP

### Data Flow (MVP Architecture)

```
Chat events:    Buyer → WebSocket (Fargate) → classify_question() inline
                → calculate_score() inline → DynamoDB write → RDS write
                → score_update via WebSocket → check_and_alert()

Non-chat events: Buyer → POST /tours/{id}/events → calculate_score()
                 → DynamoDB write → RDS write → check_and_alert()

Reconciliation: CloudWatch (5 min) → Lambda → DynamoDB scan → RDS upsert
```

---

## 5. Tour Script Schema (v1.0.0)

```json
{
  "schema_version": "1.0.0",
  "project_id": "uuid",
  "project_name": "Sunshine Heights",
  "total_rooms": 8,
  "estimated_duration_seconds": 240,
  "rooms": [{
    "index": 0,
    "id": "living_room",
    "name": "Living Room",
    "room_type": "living_room",
    "narration": {"text": "...", "duration_seconds": 30, "language": "en"},
    "visuals": {"primary_image_url": "...", "labels": [...]},
    "features": [{"name": "...", "category": "..."}],
    "transition": {"type": "slide_left", "duration_ms": 300}
  }],
  "metadata": {"generated_at": "...", "pipeline_version": "1.0.0"}
}
```

---

## 6. Redis Cache Structure

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `session:{session_id}` | 24h | Score + classification cache |
| `tour:{project_id}` | 1h | Tour script JSON cache |
| `dashboard:{cp_id}:{month}` | 60s | Dashboard stats cache |
| `otp_rate:{phone}` | 900s | OTP rate limiting (max 5) |
| `otp_attempts:{phone}` | 900s | Failed OTP attempt counter (lock at 3) |

---

## 7. Test Coverage

| Module | Tests | Framework |
|--------|-------|-----------|
| Backend (FastAPI) | 183 | pytest + hypothesis + httpx |
| Workers (Lambda) | 18 | pytest + moto |
| Infrastructure (CDK) | 37 | jest + CDK assertions |
| **Total** | **238** | — |

### Property-Based Tests (Hypothesis)

| Property | What it Tests |
|----------|---------------|
| P1: Phone validation | Accepts iff 10 digits starting 6-9 |
| P2: RERA validation | Accepts iff `RERA/[A-Z]{2}/\d{4}/\d+` |
| P3: Lead score calculation | Sum of weights, capped at 10, deduplication |
| P4: Lead classification | Correct tier per score thresholds |
| P6: Multi-tenant isolation | 403 for unassigned projects |
| P9: Tour Script round-trip | serialize(parse(x)) == x |
| P10: Validation errors | Error includes path + constraint + expected |
| P11: Unknown field tolerance | Extra fields ignored silently |
| P12: Question classification | Correct signal for keywords |
| P13: Message length | Accepts 1-500, rejects 0 and >500 |
| P14: Alert threshold | Exactly one alert when score ≥ 7 |
| P17: Room revisit detection | Recorded iff previously viewed room |
| P19: Asset upload validation | Format + size + count validation |
| P20: Processing eligibility | Eligible iff images ≥ 10 AND floor_plan == 1 |
| P21: Upload blocked by status | Blocked iff processing_in_progress or tour_ready |
| P22: Admin-only auth | Non-admin always gets 403 |
| P23: Access revocation | 403 after partnership removal |
| P24: Duplicate partnership | 409 on duplicate CP-project pair |
| P26: Pipeline sequencing | tour_sequencer only after both predecessors |

---

## 8. What's Remaining (Week 4)

| Task | Description |
|------|-------------|
| 15 | WhatsApp alerts via Gupshup + SNS fallback |
| 16 | CP dashboard endpoints (stats, hot leads, detail) |
| 17 | Share link generation + click tracking |
| 18 | Razorpay subscription billing |
| 19 | Backend API checkpoint |
| 20 | Next.js frontend — CP dashboard + auth |
| 21 | Next.js frontend — Buyer tour experience |
| 22 | Subscription management UI |
| 23 | Admin internal dashboard |
| 24 | Frontend checkpoint |
| 25 | Integration wiring + CDK deploy all |
| 26 | Final checkpoint |

---

## 9. Environment & Tooling

| Tool | Version |
|------|---------|
| Node.js | 22.23.1 (via nvm) |
| Python | 3.12.6 |
| AWS CDK | 2.172.0 |
| FastAPI | 0.109.2 |
| SQLAlchemy | 2.0.25 |
| Pydantic | 2.6.1 |
| pytest | 7.4.4 |
| hypothesis | 6.98.0 |
| TypeScript | 5.4.5 |

---

*Generated: July 1, 2026*
