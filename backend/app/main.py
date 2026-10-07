from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import ical_feed, whatsapp
from app.config import settings
from app.database import ensure_indexes
from app.notifications import _email_credentials, email_is_configured
from app.rate_limit import limiter
from app.routers import rooms, bookings, admin, congregations, booking_purposes, areas, users, auth

app = FastAPI(title="Church Booking System")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if not cors_origins:
    cors_origins = [settings.frontend_url]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rooms.router)
app.include_router(bookings.router)
app.include_router(admin.router)
app.include_router(congregations.router)
app.include_router(booking_purposes.router)
app.include_router(areas.router)
app.include_router(users.router)
app.include_router(auth.router)


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    # Shows up in the hosting logs right after a deploy, so a missing or
    # mistyped email setting is visible without having to make a booking.
    if email_is_configured():
        sender, password = _email_credentials()
        print(f"[email] configured: sending as {sender} via {settings.smtp_host}:{settings.smtp_port} (password length {len(password)})", flush=True)
    else:
        print("[email] NOT configured: set EMAIL_FROM and EMAIL_PASSWORD — booking emails will be skipped", flush=True)
    if whatsapp.is_configured():
        print(f"[whatsapp] configured: phone number id {settings.whatsapp_phone_number_id.strip()}, templates in '{settings.whatsapp_template_language}'", flush=True)
    else:
        print("[whatsapp] NOT configured: set WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN — WhatsApp messages will be skipped", flush=True)
    if ical_feed.enabled():
        print("[calendar] pulling church events from the Google Calendar iCal feed", flush=True)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
