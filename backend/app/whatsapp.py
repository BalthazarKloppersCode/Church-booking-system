"""
WhatsApp through Meta's Cloud API.

A business can only start a conversation with an approved *message template*;
free-form text is only allowed within 24 hours of the person last messaging
the number. Every notification here is business-initiated, so each one is a
template. The wording below is the single source of truth — paste each body
into Meta when creating the template (docs/WHATSAPP_SETUP.md lists them with
sample values), and `render` fills the same text in for the logs.

Like email, a failure here is logged and never raised: a WhatsApp problem must
not undo a booking.
"""
import re

import httpx

from app.config import settings

# name -> (category, body). {{1}}, {{2}}… are the positional variables Meta
# expects. Meta rejects a body that starts or ends with a variable.
TEMPLATES: dict[str, tuple[str, str]] = {
    "booking_confirmed": (
        "UTILITY",
        "Hi {{1}}, your booking for {{2}} is confirmed.\n\n"
        "Room: {{3}}\nDate: {{4}}\nTime: {{5}}\nReference: {{6}}\n\n"
        "Your full confirmation and venue conditions are saved under My bookings at {{7}}. "
        "Please keep this message for your records.",
    ),
    "booking_pending": (
        "UTILITY",
        "Hi {{1}}, we've received your request to book {{2}} on {{3}} at {{4}}.\n\n"
        "It needs approval from the office. We'll message you as soon as it has been reviewed.",
    ),
    "booking_not_approved": (
        "UTILITY",
        "Hi {{1}}, unfortunately your request to book {{2}} on {{3}} was not approved.\n\n"
        "Note from the office: {{4}}\n\n"
        "Please contact the office if you'd like to discuss alternatives.",
    ),
    "admin_new_request": (
        "UTILITY",
        "New booking request from {{1}} ({{2}}): {{3}} on {{4}} at {{5}} for {{6}} people. "
        "Reason: {{7}}.\n\nPlease review it in the admin portal.",
    ),
}


def is_configured() -> bool:
    return bool(settings.whatsapp_access_token.strip() and settings.whatsapp_phone_number_id.strip())


def normalize_phone(raw: str) -> str | None:
    """
    Digits only, with country code, as WhatsApp wants ("27821234567").
    Accepts "+27 82 123 4567", "0027821234567", "082 123 4567" (local number —
    the default country code is added). Returns None if it can't be a phone number.
    """
    text = (raw or "").strip()
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    country = re.sub(r"\D", "", settings.whatsapp_default_country_code)
    if text.startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = country + digits[1:]
    elif country and not digits.startswith(country) and len(digits) <= 10:
        digits = country + digits
    return digits if 8 <= len(digits) <= 15 else None


def clean_param(value) -> str:
    """Template variables can't hold line breaks, tabs or runs of spaces, and can't be empty."""
    text = re.sub(r"\s+", " ", str(value if value is not None else "")).strip()
    return text or "-"


def render(template: str, params: list) -> str:
    body = TEMPLATES[template][1]
    return re.sub(r"\{\{(\d+)\}\}", lambda m: clean_param(params[int(m.group(1)) - 1]), body)


async def send_template(to_phone: str, template: str, params: list) -> None:
    if template not in TEMPLATES:
        raise ValueError(f"Unknown WhatsApp template: {template}")
    if not is_configured():
        print(f"[whatsapp skipped - no credentials] to={to_phone} template={template}", flush=True)
        return
    to = normalize_phone(to_phone)
    if to is None:
        print(f"[whatsapp skipped - not a valid phone number] to={to_phone!r} template={template}", flush=True)
        return
    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id.strip()}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token.strip()}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": settings.whatsapp_template_language},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": clean_param(p)} for p in params]}
            ],
        },
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", {})
                detail = f"code {err.get('code')}: {err.get('message')}"
                if err.get("error_data", {}).get("details"):
                    detail += f" — {err['error_data']['details']}"
            except Exception:
                detail = resp.text[:300]
            print(f"[whatsapp error] to={to} template={template} {resp.status_code} {detail}", flush=True)
            return
        print(f"[whatsapp sent] to={to} template={template}", flush=True)
    except Exception as e:
        print(f"[whatsapp error] to={to} template={template} {type(e).__name__}: {e}", flush=True)
