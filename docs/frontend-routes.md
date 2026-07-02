# CP Portal Frontend Routes

**Base URL:** `http://localhost:3001`

## Pages

| Route | Auth Required | Description |
|-------|--------------|-------------|
| `/` | No | Auto-redirect: authenticated → `/dashboard`, else → `/login` |
| `/login` | No | OTP login (phone → verify → JWT) |
| `/register` | Yes | First-time CP registration (name + RERA ID) |
| `/dashboard` | Yes | Stats cards + hot leads table + real-time WebSocket |
| `/dashboard/leads/[leadId]` | Yes | Lead detail: buyer info, score, signals, session timeline |
| `/projects` | Yes | Project grid with tour status badges + WhatsApp share |
| `/billing` | Yes | Credit pack purchase via Razorpay |

## Frontend → Backend API Mapping

All API calls go through Next.js rewrite proxy: browser requests `/api/v1/...` → Next.js forwards to backend at `http://localhost:8001/api/v1/...`

### Login Page (`/login`)
| Action | Backend Endpoint | Method |
|--------|-----------------|--------|
| Send OTP | `/api/v1/auth/otp/request` | POST |
| Verify OTP | `/api/v1/auth/otp/verify` | POST |

### Register Page (`/register`)
| Action | Backend Endpoint | Method |
|--------|-----------------|--------|
| Complete registration | `/api/v1/auth/register` | POST |

### Dashboard (`/dashboard`)
| Action | Backend Endpoint | Method |
|--------|-----------------|--------|
| Load stats | `/api/v1/dashboard/stats` | GET |
| Load hot leads | `/api/v1/dashboard/hot-leads?limit=50&offset=0` | GET |
| Real-time updates | `/api/v1/dashboard/ws` | WebSocket |

### Lead Detail (`/dashboard/leads/[id]`)
| Action | Backend Endpoint | Method |
|--------|-----------------|--------|
| Load lead detail | `/api/v1/dashboard/leads/{lead_id}` | GET |

### Projects (`/projects`)
| Action | Backend Endpoint | Method |
|--------|-----------------|--------|
| Load project list | `/api/v1/projects` | GET |
| Generate share link | `/api/v1/projects/{project_id}/share-link` | POST |

### Billing (`/billing`)
| Action | Backend Endpoint | Method |
|--------|-----------------|--------|
| Load credit packs | `/api/v1/billing/packs` | GET |
| Purchase credits | `/api/v1/billing/purchase` | POST |

## Dev Mode Login

- Phone: any valid 10-digit Indian number (e.g., `8482861955`)
- OTP: **`123456`** (fixed in development mode)
- Already registered users go directly to `/dashboard`
- New users redirected to `/register`

## Running Locally

```bash
# Terminal 1: Backend (port 8001)
cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# Terminal 2: Frontend (port 3001)
cd frontend && npm run dev -- -p 3001
```

Frontend proxies all `/api/*` requests to backend via `next.config.js` rewrites.
