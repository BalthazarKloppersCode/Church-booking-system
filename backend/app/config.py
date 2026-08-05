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

    resend_api_key: str = ""
    email_from: str = "bookings@yourchurch.org"

    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""

    admin_notify_email: str = ""
    admin_notify_whatsapp: str = ""

    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
