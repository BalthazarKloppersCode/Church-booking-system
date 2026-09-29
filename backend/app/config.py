from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "church_booking"

    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_hours: int = 12

    # One-time secret required to create the very first admin account via
    # POST /api/admin/register. Leave unset to disable that endpoint until
    # you configure it. After the first admin exists, registering further
    # admins requires an existing admin's login instead of this secret.
    admin_setup_secret: str = ""

    # Comma-separated list of allowed frontend origins for CORS. Falls back
    # to frontend_url below if not set.
    cors_origins: str = ""

    auto_approve_window_days: int = 14

    # Sends via the church's real Gmail account over SMTP, authenticated
    # with a Google App Password (not the account's normal login password —
    # requires 2-Step Verification to be turned on first). email_from is
    # that Gmail address and also the SMTP login username; email_from_name
    # is just the friendly display name recipients see.
    email_from: str = "bookings@yourchurch.org"
    email_from_name: str = "Pinehurst Campus Bookings"
    email_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""

    # Google Calendar two-way sync (e.g. "LINKTREE Durbanville AM Events").
    # google_service_account_json is the *contents* of a Google service
    # account key file (paste the whole JSON as one line), not a file path —
    # share the target calendar with that service account's email, with
    # "Make changes to events" permission. Leave blank to disable sync
    # entirely (every call becomes a no-op, same as the email/WhatsApp keys).
    google_service_account_json: str = ""
    google_calendar_id: str = ""

    admin_notify_email: str = ""
    admin_notify_whatsapp: str = ""

    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
