# Church Campus Room Booking System

A booking portal for classrooms, training halls, and the main hall, plus an
admin portal for approvals, a room grid ("top view"), and a calendar.

- Bookings **≤ 14 days out**, non-private → **auto-confirmed instantly**
- Bookings **> 14 days out**, OR marked **private** (weddings, funerals, etc.)
  → go to the **admin approval queue**
- Booker enters headcount → system suggests rooms that fit
- Confirmations include the room's "leave it like this" setup notes
- Notifications sent by **email** (Resend) and **WhatsApp** (Meta Cloud API)

## Stack

- Backend: FastAPI + MongoDB (Motor async driver)
- Frontend: React (Vite) + react-router + react-big-calendar
- Auth: JWT for admins; bookers identify with just name/email/phone (no password)

## Project layout

```
backend/
  app/
    main.py            FastAPI app + CORS
    config.py           Settings loaded from .env
    database.py          Mongo connection + indexes
    models.py            Pydantic schemas
    auth.py               Admin password hashing + JWT
    notifications.py      Email (Resend) + WhatsApp (Meta Cloud API) senders
    routers/
      rooms.py            Room CRUD + /suggest (capacity-based matching)
      bookings.py         Create/list/cancel bookings, auto-approve logic
      admin.py             Login, approvals queue, approve/reject, dashboard
  seed_data.py            Placeholder rooms — EDIT THESE to your real rooms
  requirements.txt
  .env.example

frontend/
  src/
    pages/
      HomePage.jsx
      BookPage.jsx        Public booking wizard (4 steps)
      MyBookingsPage.jsx   Look up / cancel bookings by email
      admin/
        AdminLogin.jsx
        AdminLayout.jsx     Sidebar shell, guards routes via /api/admin/me
        AdminDashboard.jsx
        AdminApprovals.jsx
        AdminRoomGrid.jsx   Top view: all rooms x one day
        AdminCalendar.jsx   Full calendar, filterable by room
        AdminRooms.jsx      Add/edit rooms + setup notes
    lib/
      api.js              Fetch wrapper for the backend
      useAdmin.js          Auth guard hook
  .env.example
```

## Free hosting plan ($0/month at church scale)

| Piece | Service | Free tier |
|---|---|---|
| Database | [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register) | M0 cluster, 512MB |
| Backend | [Render](https://render.com) | Free web service (sleeps after 15 min idle — first request after that takes ~30s to wake up) |
| Frontend | [Vercel](https://vercel.com) | Free static hosting |
| Email | [Resend](https://resend.com) | 3,000 emails/month |
| WhatsApp | [Meta WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api) | 1,000 service conversations/month |

## Setup

### 1. Database
1. Create a free MongoDB Atlas account and an M0 cluster.
2. Create a database user, allow network access from anywhere (0.0.0.0/0) or Render's IPs.
3. Copy the connection string into `backend/.env` as `MONGO_URI`.

### 2. Backend
```bash
cd backend
cp .env.example .env      # fill in MONGO_URI at minimum
pip install -r requirements.txt --break-system-packages
python seed_data.py        # loads placeholder rooms — edit ROOMS list first
uvicorn app.main:app --reload
```
Visit `http://localhost:8000/docs` for interactive API docs.

Set `ADMIN_SETUP_SECRET` in `backend/.env` to a long random value, then create your first
admin account (the setup secret is only required for this very first admin — once one
exists, further admins must be created by an already-logged-in admin via the same route):
```bash
curl -X POST http://localhost:8000/api/admin/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Admin","email":"admin@yourchurch.org","password":"choose-a-strong-password","setup_secret":"the-ADMIN_SETUP_SECRET-value"}'
```

### 3. Frontend
```bash
cd frontend
cp .env.example .env       # set VITE_API_URL to your backend URL
npm install
npm run dev
```

### 4. Email (Resend)
1. Sign up at resend.com, verify a sending domain (or use their test domain while developing).
2. Put the API key in `backend/.env` as `RESEND_API_KEY`, and set `EMAIL_FROM`.

### 5. WhatsApp (Meta Cloud API)
1. Create a Meta Business account and a WhatsApp Business app at developers.facebook.com.
2. Get a phone number ID and a permanent access token.
3. Put them in `backend/.env` as `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_ACCESS_TOKEN`.
4. Note: outside Meta's 24-hour customer service window, WhatsApp requires pre-approved
   message templates rather than free-form text. The current `notifications.py` sends
   free-form messages, which works for the first message in a conversation window — for
   production reliability you may want to register templates for booking confirmed /
   pending / rejected messages. Flagging this as a near-term follow-up, not blocking for launch.

### 6. Deploy
- **Backend → Render**: New Web Service, connect the repo, root directory `backend`,
  build command `pip install -r requirements.txt`, start command
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Add all `.env` vars in Render's
  dashboard.
- **Frontend → Vercel**: New Project, root directory `frontend`, framework preset Vite.
  Add `VITE_API_URL` pointing to your Render backend URL.
- Update the backend's CORS `allow_origins` in `app/main.py` from `["*"]` to your actual
  Vercel URL once deployed.

## Not yet built / next steps
- Admin UI to create additional admin accounts (currently only via the API/curl)
- WhatsApp template messages for reliability outside the 24-hour session window
- Recurring bookings (e.g. weekly youth group same room/time)
- Room photos upload (model already has a `photo_url` field, just needs an upload flow)
- Real room list (placeholders are in `backend/seed_data.py` — replace with your campus's actual rooms)
