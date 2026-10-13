"""
One-time registration of the church's WhatsApp number with Meta's Cloud API.

After you add and verify the number in WhatsApp Manager it shows "Pending —
please register this phone number using the registration API". This script
makes that call. Run it from the backend folder once your Phone number ID and
access token are in backend/.env:

    python register_whatsapp_number.py            # registers (asks for a 6-digit PIN)
    python register_whatsapp_number.py --status   # just shows the number's status

The PIN is one you choose now (6 digits). It's the number's two-step
verification PIN — keep it somewhere safe, Meta asks for it if the number is
ever re-registered. It is typed hidden and never printed or stored.
"""
import getpass
import sys

import httpx

from app.config import settings


def main() -> int:
    phone_id = settings.whatsapp_phone_number_id.strip()
    token = settings.whatsapp_access_token.strip()
    if not phone_id or not token:
        print("Set WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN in backend/.env first.")
        return 1
    base = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{phone_id}"
    headers = {"Authorization": f"Bearer {token}"}

    if "--status" not in sys.argv:
        pin = getpass.getpass("Choose a 6-digit PIN for this number (hidden): ").strip()
        again = getpass.getpass("Type it again: ").strip()
        if pin != again or not (pin.isdigit() and len(pin) == 6):
            print("The PIN must be exactly 6 digits and typed the same both times.")
            return 1
        resp = httpx.post(f"{base}/register", headers=headers, json={"messaging_product": "whatsapp", "pin": pin}, timeout=30)
        print(f"Register: {resp.status_code} {resp.text}")
        if resp.status_code >= 400:
            return 1

    resp = httpx.get(
        base,
        headers=headers,
        params={"fields": "display_phone_number,verified_name,status,code_verification_status,quality_rating,name_status"},
        timeout=30,
    )
    print(f"Status: {resp.status_code} {resp.text}")
    return 0 if resp.status_code < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
