# Handoff: Church Campus Room Booking System

Context for continuing this project in Claude Code. Paste this whole file into
Claude Code as your opening prompt (or point it at this file in the repo) so it
has full context without you re-explaining everything.

## The ask (from the church admin, verbatim intent)

We have a campus building with classrooms, training halls, and a main hall.
Right now everyone messages one person to check availability — we want a
self-serve booking portal instead, plus an admin portal for oversight.

Requirements:
- Anyone can book a classroom, training hall, or main hall **up to 2 weeks in
  advance** — this should be instant, no approval needed.
- Anything **more than 2 weeks out** needs **admin approval**.
- **Private bookings** (weddings, funerals, etc.) **always** need approval,
  regardless of how far out they are.
- When booking, the person fills in: which congregation/group is booking, and
  how many people are expected. The system should **suggest rooms** based on
  that headcount.
- Once a booking is confirmed, send the person info on **what the room needs
  to look like when they're done** (setup/breakdown instructions).
- Admin portal needs: a **dashboard**, a **top-view/grid of all rooms**
  (at-a-glance status), and a **full calendar view**.
- **No budget** — everything must run on free tiers.
- Notifications go out via **both email and WhatsApp**.
- Booking users should **not** need to create an account (name/email/phone per
  booking is enough). Admins **do** need a login.

## Decisions already made and why

1. **Stack: FastAPI + MongoDB (Motor) + React (Vite)** — chosen to match the
   user's existing stack on their other internal product (AXIS), so they're
   not learning new tooling.
2. **Auth model**: bookers are identified by email/name/phone with no
   password (like OpenTable) — their email is the key to look up/cancel their
   own bookings later. Admins have a real email+password login with JWT.
3. **Free hosting plan**: MongoDB Atlas (M0 free tier) + Render (backend,
   free web service) + Vercel (frontend, free static hosting) + Resend
   (email, 3,000/mo free) + Meta WhatsApp Cloud API (1,000 free service
   conversations/mo). Full reasoning and setup steps are in `README.md`.
4. **Auto-approve window**: configurable via `AUTO_APPROVE_WINDOW_DAYS` env
   var, defaults to 14 days, enforced in `backend/app/routers/bookings.py`
   inside `create_booking`.
5. **Room suggestion logic**: `/api/rooms/suggest` ranks active rooms by
   capacity ≥ headcount (smallest sufficient room first), flags whether
   they're actually free for the requested time slot, and tags fit quality
   (`good_fit` / `oversized` / `too_small`). If nothing meets the headcount it
   falls back to the largest available rooms rather than returning empty.
6. **Design direction**: warm sage/teal palette (not the generic cream +
   terracotta AI-design cliché), Fraunces for headings + Inter for body,
   deliberately calm/utility-first since this is an internal tool, not a
   marketing site. Tokens live in `frontend/src/index.css`.

## Current status: working scaffold, not yet deployed

### Backend — fully implemented, import/syntax verified, NOT tested against a
real running MongoDB instance (no MongoDB available in the sandbox this was
built in — Claude Code should spin one up locally with Docker or point it at
a real Atlas cluster and smoke-test the flows below).

Endpoints that exist:
- `GET/POST /api/rooms`, `PATCH/DELETE /api/rooms/{id}`, `POST /api/rooms/suggest`
- `POST /api/bookings`, `GET /api/bookings` (filterable by email/room_id/status/date range), `POST /api/bookings/{id}/cancel`
- `POST /api/admin/register`, `POST /api/admin/login`, `GET /api/admin/me`
- `GET /api/admin/approvals`, `POST /api/admin/bookings/{id}/approve`, `POST /api/admin/bookings/{id}/reject`
- `GET /api/admin/dashboard`

Known gaps / things to check first:
- `/api/admin/register` is open (no auth required) — that's intentional for
  first-run setup but **must be locked down or removed** before going live
  publicly. Noted in README but not yet implemented.
- No rate limiting anywhere — a public booking form is a spam target.
- No tests written at all yet.
- WhatsApp sending uses free-form messages via the Cloud API, which only
  works within a 24-hour customer-service session window. For a real launch
  this likely needs pre-approved message templates instead — flagged in
  README under "Not yet built."
- CORS is wide open (`allow_origins=["*"]`) — needs tightening to the real
  frontend domain before launch.

### Frontend — builds cleanly with `npm run build`, not yet run against a
live backend (only smoke-tested via `vite build`, not manually clicked
through in a browser).

Pages that exist: `HomePage`, `BookPage` (4-step wizard), `MyBookingsPage`,
`AdminLogin`, `AdminLayout` (sidebar shell + route guard), `AdminDashboard`,
`AdminApprovals`, `AdminRoomGrid`, `AdminCalendar`, `AdminRooms`.

Known gaps:
- No loading/error skeletons beyond basic "Loading…" text.
- No mobile-specific polish pass done — should still be responsive since it's
  plain CSS flex/grid, but hasn't been visually checked at narrow widths.
- Placeholder rooms are seeded via `backend/seed_data.py` — real room list
  and capacities still need to be entered (either edit that script or use
  the Manage Rooms admin page after deploy).
- No favicon/branding beyond Vite defaults.

## Immediate next steps, in order

1. Spin up a local MongoDB (Docker: `docker run -p 27017:27017 mongo`) or
   create the Atlas cluster, and actually run the backend end-to-end:
   create a room, create a booking (both auto-approved and pending paths),
   approve/reject via admin, confirm the calendar and room grid reflect it.
2. Manually click through the frontend against that running backend —
   this has NOT been done yet, only `npm run build` has been verified.
3. Lock down `/api/admin/register` (e.g. require an existing admin's token,
   or a one-time setup secret from env).
4. Wire up real Resend and Meta WhatsApp Cloud API credentials and confirm a
   real notification round-trip.
5. Deploy per the README (Render + Vercel + Atlas), tighten CORS.
6. Replace placeholder rooms with the church's real room list.

## Files worth reading first in Claude Code

- `README.md` — full setup/deploy instructions
- `backend/app/routers/bookings.py` — the core approval-logic decision point
- `backend/app/notifications.py` — email/WhatsApp sending, all the message copy
- `frontend/src/pages/BookPage.jsx` — the main user-facing flow
- `frontend/src/pages/admin/AdminApprovals.jsx` — the core admin action
