# Implementation Plan: AutoMind AI Platform

## Overview

Implement the AutoMind AI Platform following a 4-week build priority: Infrastructure + Auth (Week 1), AI Pipeline (Week 2), Buyer Experience (Week 3), and Lead Engine + Launch (Week 4). The stack uses Next.js 14 (TypeScript) for frontend, FastAPI (Python 3.11) for backend, AWS CDK (TypeScript) for infrastructure, and leverages AWS Bedrock, Rekognition, Textract, DynamoDB, RDS Postgres, ECS Fargate, and Lambda.

## Tasks

- [ ] 1. Set up infrastructure foundation (CDK stacks and shared resources)
  - [x] 1.1 Initialize AWS CDK project with shared constructs
    - Create `infra/` directory with CDK TypeScript project
    - Define VPC stack (public/private subnets, NAT gateway)
    - Define S3 bucket constructs (assets, tour-scripts, CDN origin)
    - Define DynamoDB `automind_sessions` table with GSI1 (CP#{cp_id} / SCORE#{...})
    - Define RDS PostgreSQL instance (db.t3.medium, private subnet)
    - Define ElastiCache Redis cluster (cache.t3.micro)
    - Define SQS queues (processing-queue, dead-letter-queue)
    - Define CloudFront distribution with Route 53 DNS
    - _Requirements: 9.5, 11.1, 12.4_

  - [x] 1.2 Define ECS Fargate service and ALB stack
    - Create ECS cluster with Fargate service for FastAPI
    - Configure ALB with health check and target group
    - Define task definition with environment variables and secrets
    - Configure auto-scaling (min 1, max 4 tasks)
    - _Requirements: 8.1, 8.2_

  - [x] 1.3 Define Lambda functions stack
    - Create Lambda constructs for: image_analyzer, pdf_extractor, tour_sequencer, kb_builder, lead_scorer
    - Create Lambda for background reconciliation (scheduled every 5 min)
    - Configure SQS event sources for pipeline Lambdas
    - Configure CloudWatch Events trigger for reconciliation Lambda
    - Set IAM roles with least-privilege policies
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 1.4 Define Cognito User Pool and API Gateway WebSocket
    - Create Cognito User Pool with phone number as username
    - Configure OTP custom auth challenge Lambda triggers
    - Create API Gateway WebSocket API with routes ($connect, $disconnect, chat, room_navigate)
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2. Implement FastAPI skeleton and database layer
  - [x] 2.1 Create FastAPI project structure with core dependencies
    - Initialize `backend/` directory with FastAPI, uvicorn, asyncpg, aioboto3, pydantic
    - Create project structure: `app/`, `app/api/`, `app/core/`, `app/models/`, `app/services/`, `app/schemas/`
    - Implement health check endpoint `GET /health`
    - Configure CORS, middleware, and exception handlers
    - Set up structured logging with request_id tracking
    - _Requirements: 8.1_

  - [x] 2.2 Implement RDS PostgreSQL schema and migrations
    - Create Alembic migrations for all tables: cps, builders, projects, partnerships, share_links, project_assets, processing_jobs, subscriptions, leads, admins
    - Create all indexes as defined in design
    - Write database connection pool setup with asyncpg
    - _Requirements: 12.1, 12.2, 16.1, 16.2_

  - [x] 2.3 Implement DynamoDB session repository
    - Create DynamoDB client wrapper with connection reuse
    - Implement session CRUD: create_session, get_session, update_score, add_event
    - Implement GSI1 query for CP hot leads sorted by score
    - Configure TTL of 30 days on session items
    - _Requirements: 9.5, 5.1_

  - [x] 2.4 Implement Redis cache layer
    - Create Redis client with connection pooling
    - Implement session score cache (TTL 24h)
    - Implement tour script cache (TTL 1h)
    - Implement dashboard stats cache (TTL 60s)
    - Implement OTP rate limiting counters (TTL 900s)
    - _Requirements: 1.7, 2.1_

- [x] 3. Implement CP authentication via OTP
  - [x] 3.1 Implement phone number validation and OTP request endpoint
    - Create `POST /api/v1/auth/otp/request` endpoint
    - Implement Indian phone number validation (10 digits, starts with 6-9)
    - Integrate with Cognito `InitiateAuth` for custom auth challenge
    - Implement rate limiting: max 5 OTPs per phone per 15 minutes
    - Return 429 with retry_after when rate limited
    - _Requirements: 1.1, 1.7, 1.8_

  - [x]* 3.2 Write property test for phone number validation
    - **Property 1: Indian Phone Number Validation**
    - Generate random strings: valid 10-digit numbers starting with 6-9 + invalid strings (wrong length, wrong prefix, non-numeric)
    - Assert: accepts if and only if exactly 10 digits starting with 6-9
    - **Validates: Requirements 1.1, 1.8, 5.4**

  - [x] 3.3 Implement OTP verification and token issuance
    - Create `POST /api/v1/auth/otp/verify` endpoint
    - Verify OTP via Cognito `RespondToAuthChallenge`
    - Issue JWT session token with 24-hour expiry on success
    - Track failed attempts: lock phone for 15 min after 3 consecutive failures
    - Return 401 with attempts_remaining on wrong OTP
    - Return 423 with unlock_at on lockout
    - Handle OTP expiry (5-minute window)
    - _Requirements: 1.2, 1.3, 1.4_

  - [x] 3.4 Implement CP registration endpoint
    - Create `POST /api/v1/auth/register` endpoint (requires auth)
    - Validate RERA_ID format: `RERA/{state_code}/{year}/{number}`
    - Create CP record in RDS with phone, name, rera_id, cognito_sub
    - Return 422 for invalid RERA format
    - _Requirements: 1.5_

  - [x]* 3.5 Write property test for RERA ID validation
    - **Property 2: RERA ID Format Validation**
    - Generate random strings conforming and not conforming to `RERA/{state}/{year}/{number}`
    - Assert: accepts if and only if pattern matches
    - **Validates: Requirements 1.5**

  - [x] 3.6 Implement anonymous session creation for buyers
    - Create `POST /api/v1/auth/session/anonymous` endpoint
    - Generate unique session_id, store in DynamoDB with CP/project attribution
    - Return session_token (JWT) for WebSocket auth
    - Handle return-visit detection via link_id matching
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

- [ ] 4. Checkpoint - Infrastructure and Auth
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement admin endpoints and partnership management
  - [x] 5.1 Implement project creation endpoint
  - [x]* 5.2 Write property test for admin-only authorization
  - [x] 5.3 Implement CP-to-project partnership assignment
  - [x]* 5.4 Write property test for duplicate partnership rejection
  - [x] 5.5 Implement partnership removal and access revocation
  - [x]* 5.6 Write property test for access revocation immediacy
  - [x] 5.7 Implement multi-tenant data isolation middleware
  - [x]* 5.8 Write property test for multi-tenant isolation

- [x] 6. Implement asset upload and processing pipeline trigger
  - [x] 6.1 Implement asset upload endpoint with validation
  - [x]* 6.2 Write property test for asset upload validation
  - [x]* 6.3 Write property test for upload blocked by project status
  - [x] 6.4 Implement processing trigger endpoint
  - [x]* 6.5 Write property test for processing eligibility

- [x] 7. Implement AI processing pipeline Lambda workers
  - [x] 7.1 Implement image_analyzer Lambda worker
  - [x] 7.2 Implement pdf_extractor Lambda worker
  - [x] 7.3 Implement tour_sequencer Lambda worker
  - [x]* 7.4 Write property test for pipeline sequencing constraint
  - [x] 7.5 Implement kb_builder Lambda worker
  - [x] 7.6 Implement pipeline orchestration and status management

- [x] 8. Checkpoint - AI Pipeline complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement Tour Script schema and validation
  - [x] 9.1 Define Tour_Script JSON schema and Pydantic models
  - [x]* 9.2 Write property test for Tour Script round-trip serialization
  - [x]* 9.3 Write property test for Tour Script validation errors
  - [x]* 9.4 Write property test for unknown field tolerance

- [x] 10. Implement lead scoring engine
  - [x] 10.1 Implement lead score calculation function
  - [x]* 10.2 Write property test for lead score calculation
  - [x] 10.3 Implement lead classification function
  - [x]* 10.4 Write property test for lead classification
  - [x] 10.5 Implement question classification for chat signals
  - [x]* 10.6 Write property test for question classification and signal application
  - [x] 10.7 Implement dual-write persistence (DynamoDB → RDS)
  - [x] 10.8 Implement alert threshold check and notification trigger
  - [x]* 10.9 Write property test for alert triggered at threshold

- [x] 11. Implement lead_scorer Lambda (non-chat events)
  - [x] 11.1 Implement lead_scorer Lambda handler
  - [x] 11.2 Implement tour event POST endpoint
  - [x]* 11.3 Write property test for room revisit event detection

- [x] 12. Implement WebSocket chat handler with inline scoring
  - [x] 12.1 Implement WebSocket connection manager on Fargate
  - [x] 12.2 Implement chat message handling with RAG integration
  - [x]* 12.3 Write property test for chat message length validation
  - [x] 12.4 Implement inline lead scoring in WebSocket handler

- [x] 13. Implement background reconciliation Lambda
  - [x] 13.1 Implement DynamoDB-to-RDS reconciliation Lambda

- [x] 14. Checkpoint - Lead Engine and WebSocket complete

- [x] 15. Implement hot-lead alert notification service
  - [x] 15.1 Implement WhatsApp alert via Gupshup with SNS fallback

  - [x]* 15.2 Write property test for alert message completeness

- [x] 16. Implement CP dashboard endpoints
  - [x] 16.1 Implement dashboard stats endpoint
  - [x] 16.2 Implement hot leads list endpoint
  - [x]* 16.3 Write property test for hot leads sorted descending
  - [x] 16.4 Implement lead detail endpoint
  - [x] 16.5 Implement dashboard WebSocket push for real-time updates

- [x] 17. Implement project selection and share link generation
  - [x] 17.1 Implement project listing endpoint
  - [x] 17.2 Implement share link generation endpoint
  - [x]* 17.3 Write property test for share link identifiers
  - [x] 17.4 Implement share link click tracking
  - [x]* 17.5 Write property test for session attribution
  - [x]* 17.6 Write property test for last-click attribution

- [x] 18. Implement credit-based billing system
  - [x] 18.1 Create credit_transactions table and add credit_balance to cps
  - [x] 18.2 Implement credit pack purchase endpoints
  - [x] 18.3 Implement Razorpay webhook for payment confirmation
  - [x] 18.4 Implement credit deduction on project processing
  - [x]* 18.5 Write property test for credit deduction atomicity

- [ ] 19. Checkpoint - Backend APIs complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 20. Implement Next.js frontend - CP dashboard and auth
  - [ ] 20.1 Set up Next.js 14 project with App Router
    - Initialize `frontend/` directory with Next.js 14, TypeScript, Tailwind CSS
    - Configure app directory structure: `app/`, `app/(auth)/`, `app/(dashboard)/`, `app/(tour)/`
    - Set up API client with axios/fetch and JWT token management
    - Configure environment variables for API base URL and WebSocket URL
    - _Requirements: 1.1, 2.1_

  - [ ] 20.2 Implement CP login flow (OTP request + verify + register)
    - Create login page with phone number input and validation
    - Create OTP verification page with 6-digit input and countdown timer
    - Create registration page for first-time users (name + RERA_ID)
    - Handle lockout state display with remaining time
    - Handle rate limit display with cooldown countdown
    - Store JWT token in httpOnly cookie
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 1.8_

  - [ ] 20.3 Implement CP dashboard page
    - Create dashboard layout with stats cards (tours shared, leads, hot leads, conversions)
    - Create hot leads list component (sorted by score, max 50)
    - Implement WebSocket connection for real-time hot lead updates
    - Create lead detail modal/page with signals, events timeline
    - Handle zero-state (no leads) with appropriate messaging
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 20.4 Implement project selection and share link UI
    - Create project grid/list with status badges (tour_ready, processing, failed, not_started)
    - Handle tour_ready → share link generation screen
    - Handle processing_in_progress → show processing message
    - Handle processing_failed → show error with retry option
    - Create share link page with WhatsApp share button and Open Graph preview
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.5_

- [ ] 21. Implement Next.js frontend - Buyer tour experience
  - [ ] 21.1 Implement tour viewer with room navigation
    - Create tour viewer page at `/t/{link_id}` route
    - Load Tour_Script and render first room within 2 seconds
    - Implement room navigation (next/previous) with CSS transitions (300ms)
    - Disable previous button on first room, next button on last room
    - Track time spent per room in whole seconds
    - Detect room revisits and post events to API
    - Trigger `time_on_tour_3min_plus` event when total exceeds 3 minutes
    - Handle Tour_Script load failure with error message
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [ ]* 21.2 Write property test for room navigation boundaries
    - **Property 16: Room Navigation Boundary Controls**
    - Generate random Tour_Scripts with varying room counts (1 to N)
    - Assert: previous disabled at index 0, next disabled at index N-1
    - **Validates: Requirements 6.7**

  - [ ] 21.3 Implement Priya avatar SVG component
    - Create SVG avatar component with three size variants: badge (48×48), header (38×38), CTA (64×64)
    - Implement idle state (closed mouth) as default
    - Implement speaking animation: alternate SVG path "d" attribute every 280ms
    - Listen for WebSocket `talking_start` → begin animation within 50ms
    - Listen for WebSocket `talking_end` → stop animation within 50ms
    - Implement 30-second timeout: stop animation if no `talking_end` received
    - Stop animation on WebSocket disconnect
    - Support `prefers-reduced-motion`: show static open-mouth instead of animation
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ] 21.4 Implement chat interface with WebSocket streaming
    - Create chat UI with message input (1-500 char validation)
    - Establish WebSocket connection with session_token auth
    - Send `{ action: "chat", message }` on submit
    - Render streaming tokens as they arrive (`chat_token` events)
    - Display full response on `chat_end`
    - Show typing indicator during `talking_start` → `talking_end`
    - Handle KB timeout with retry option
    - Handle fallback messages (no results / low confidence)
    - Implement auto-reconnect on disconnect (3 attempts, exponential backoff)
    - _Requirements: 8.1, 8.2, 8.7, 8.8, 8.9_

  - [ ] 21.5 Implement buyer contact collection and visit booking
    - Create contact form (name + phone) triggered on visit_booking_clicked or contact_cp button
    - Validate 10-digit Indian phone number
    - Post `visit_booking_clicked` event to API
    - Post buyer contact info to update session
    - _Requirements: 5.4, 9.6_

- [ ] 22. Implement subscription management UI
  - [ ] 22.1 Implement billing plans page and payment flow
    - Create billing plans page showing unlimited and per-project options
    - Integrate Razorpay checkout (redirect to short_url)
    - Handle payment success, failure, and timeout (5 min)
    - Show subscription status on dashboard
    - Display grace period warning when subscription expiring
    - _Requirements: 13.1, 13.2, 13.3, 13.5, 13.6_

- [ ] 23. Implement admin internal dashboard
  - [ ] 23.1 Implement admin project and partnership management UI
    - Create admin layout with auth guard (admin role check)
    - Create project creation form (name, builder, location, unit types)
    - Create CP assignment interface (assign/remove CP to project)
    - Create asset upload interface with drag-and-drop (images, videos, brochures, floor plans)
    - Show upload progress and validation errors
    - Create processing trigger button (enabled only when eligibility met)
    - Show pipeline status with progress indicator
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 17.1, 17.9, 17.10_

- [ ] 24. Checkpoint - Frontend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 25. Integration wiring and end-to-end flows
  - [ ] 25.1 Wire CDK deployment with all stacks
    - Create CDK app entry point that composes all stacks
    - Wire environment variables and secrets between stacks
    - Configure CloudFront origins (ALB for API, S3 for static assets)
    - Set up Route 53 DNS records
    - Configure API Gateway WebSocket with Lambda integrations
    - Deploy Cognito triggers (create-auth-challenge, verify-auth-challenge, define-auth-challenge)
    - _Requirements: 1.1, 8.1, 11.1_

  - [ ] 25.2 Wire notification flow end-to-end
    - Connect lead_scorer alert trigger → Gupshup WhatsApp API
    - Connect Fargate inline scoring alert → Gupshup WhatsApp API
    - Configure SNS SMS fallback on WhatsApp failure
    - Wire dashboard WebSocket push on new hot lead
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 2.3_

  - [ ] 25.3 Wire processing pipeline end-to-end
    - Connect S3 upload events → SQS queue → Lambda workers
    - Wire stage completion signals between workers (image_analysis + pdf_extraction → tour_sequencing → kb_building)
    - Connect pipeline completion → project status update → admin notification
    - Configure DLQ and retry policies
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

  - [ ]* 25.4 Write integration tests for critical flows
    - Test auth flow: OTP request → verify → token issuance
    - Test chat flow: WebSocket connect → chat message → stream response → score update
    - Test scoring flow: event POST → lead_scorer → DynamoDB + RDS write → alert
    - Test multi-tenant: cross-CP access returns 403
    - _Requirements: 1.1, 1.2, 8.1, 9.1, 10.1, 12.1_

- [ ] 26. Final checkpoint - All systems integrated
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 27. Production deployment and DNS
  - [ ] 27.1 Deploy CP Portal backend to ECS with updated CORS
    - Build Docker image with production CORS (CloudFront + ALB domains)
    - Push to ECR and force ECS redeployment
    - Run Alembic migrations on production RDS
    - Verify health endpoint responds on ALB
  - [ ] 27.2 Deploy frontend to S3 + CloudFront
    - Build Next.js static export with production API URL
    - Upload to CDN origin S3 bucket
    - Invalidate CloudFront cache
    - Verify frontend loads on CloudFront domain
  - [ ] 27.3 Seed demo data for working demo
    - Create builder, project, partnership in production DB
    - Register a test CP via OTP flow
    - Verify full login → dashboard → projects flow works
  - [ ] 27.4 Configure HTTPS (ACM + ALB)
    - Request ACM certificate for ALB (or use CloudFront HTTPS which is already enabled)
    - Add HTTPS listener to ALB (when custom domain available)
  - [ ] 27.5 GitHub Actions CI/CD pipeline
    - Automate: push to main → build → test → deploy backend → deploy frontend

## Notes

- Tasks marked with `*` are optional property-based test tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints (tasks 4, 8, 14, 19, 24, 26) ensure incremental validation
- Property tests use Hypothesis (Python) for backend and fast-check (TypeScript) for frontend
- Unit tests complement property tests for specific scenarios and edge cases
- The 4-week build priority is: Infrastructure+Auth (tasks 1-4), AI Pipeline (tasks 5-8), Buyer Experience (tasks 9-14, 20-21), Lead Engine+Launch (tasks 15-19, 22-26)
- Dual-write pattern (DynamoDB → RDS) is shared between Fargate inline scoring and lead_scorer Lambda via `persist_score_update()`
- Background reconciliation Lambda (task 13) catches any missed RDS writes

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 4, "tasks": ["3.1", "3.6"] },
    { "id": 5, "tasks": ["3.2", "3.3"] },
    { "id": 6, "tasks": ["3.4", "3.5"] },
    { "id": 7, "tasks": ["5.1", "5.7"] },
    { "id": 8, "tasks": ["5.2", "5.3", "5.5"] },
    { "id": 9, "tasks": ["5.4", "5.6", "5.8"] },
    { "id": 10, "tasks": ["6.1", "6.4"] },
    { "id": 11, "tasks": ["6.2", "6.3", "6.5"] },
    { "id": 12, "tasks": ["7.1", "7.2"] },
    { "id": 13, "tasks": ["7.3"] },
    { "id": 14, "tasks": ["7.4", "7.5"] },
    { "id": 15, "tasks": ["7.6"] },
    { "id": 16, "tasks": ["9.1"] },
    { "id": 17, "tasks": ["9.2", "9.3", "9.4"] },
    { "id": 18, "tasks": ["10.1", "10.3", "10.5"] },
    { "id": 19, "tasks": ["10.2", "10.4", "10.6", "10.7", "10.8"] },
    { "id": 20, "tasks": ["10.9", "11.1", "11.2"] },
    { "id": 21, "tasks": ["11.3", "12.1"] },
    { "id": 22, "tasks": ["12.2", "12.4"] },
    { "id": 23, "tasks": ["12.3", "13.1"] },
    { "id": 24, "tasks": ["15.1"] },
    { "id": 25, "tasks": ["15.2", "16.1", "16.2"] },
    { "id": 26, "tasks": ["16.3", "16.4", "16.5"] },
    { "id": 27, "tasks": ["17.1", "17.2"] },
    { "id": 28, "tasks": ["17.3", "17.4"] },
    { "id": 29, "tasks": ["17.5", "17.6", "18.1"] },
    { "id": 30, "tasks": ["18.2", "18.3"] },
    { "id": 31, "tasks": ["18.4"] },
    { "id": 32, "tasks": ["20.1"] },
    { "id": 33, "tasks": ["20.2", "20.3", "20.4"] },
    { "id": 34, "tasks": ["21.1"] },
    { "id": 35, "tasks": ["21.2", "21.3"] },
    { "id": 36, "tasks": ["21.4", "21.5"] },
    { "id": 37, "tasks": ["22.1", "23.1"] },
    { "id": 38, "tasks": ["25.1"] },
    { "id": 39, "tasks": ["25.2", "25.3"] },
    { "id": 40, "tasks": ["25.4"] }
  ]
}
```
