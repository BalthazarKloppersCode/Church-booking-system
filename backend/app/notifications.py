"""
Sends booking confirmations, approval requests, and status updates
via email (Resend) and WhatsApp (Meta Cloud API).

Both providers are free at the volume a single church campus will use:
- Resend free tier: 3,000 emails/month
- Meta WhatsApp Cloud API: 1,000 free service conversations/month

If API keys are not set in .env, calls are skipped and logged instead of
raising errors, so the booking flow still works during setup/testing.
"""
import asyncio

import httpx
import resend
from app.config import settings

resend.api_key = settings.resend_api_key


def _room_setup_block(room_name: str, setup_notes: str | None) -> str:
    if not setup_notes:
        return ""
    return f"\n\nWhen you're done with {room_name}, please leave it like this:\n{setup_notes}"


def _room_message_block(room: dict) -> str:
    block = ""
    if room.get("booking_message"):
        block += f"\n\n{room['booking_message']}"
    photo_urls = room.get("photo_urls") or []
    if photo_urls:
        block += "\n\nPhotos of the room:\n" + "\n".join(photo_urls)
    return block


async def send_email(to: str, subject: str, body: str):
    if not settings.resend_api_key:
        print(f"[email skipped - no RESEND_API_KEY] to={to} subject={subject}")
        return
    try:
        # resend's SDK is a blocking/sync HTTP call — running it directly in
        # an async function would stall the whole event loop (every other
        # concurrent request) for the round-trip. Push it to a thread instead.
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": settings.email_from,
                "to": [to],
                "subject": subject,
                "text": body,
            },
        )
    except Exception as e:
        print(f"[email error] {e}")


async def send_whatsapp(to_phone: str, message: str):
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        print(f"[whatsapp skipped - no credentials] to={to_phone} message={message}")
        return
    url = f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code >= 400:
                print(f"[whatsapp error] {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[whatsapp error] {e}")


async def notify_booking_confirmed(booking: dict, room: dict):
    subject = f"Booking confirmed: {room['name']} on {booking['start_time'].strftime('%d %b %Y, %H:%M')}"
    body = (
        f"Hi {booking['requester_name']},\n\n"
        f"Your booking for {room['name']} is confirmed.\n\n"
        f"Date: {booking['start_time'].strftime('%A, %d %B %Y')}\n"
        f"Time: {booking['start_time'].strftime('%H:%M')} - {booking['end_time'].strftime('%H:%M')}\n"
        f"Expected attendance: {booking['headcount']}\n"
        f"Purpose: {booking['purpose']}"
        f"{_room_setup_block(room['name'], room.get('setup_notes'))}"
        f"{_room_message_block(room)}\n\n"
        f"If you need to change or cancel this booking, contact the admin office."
    )
    await asyncio.gather(send_email(booking["email"], subject, body), send_whatsapp(booking["phone"], body))


async def notify_booking_pending(booking: dict, room: dict):
    subject = f"Booking request received: {room['name']}"
    body = (
        f"Hi {booking['requester_name']},\n\n"
        f"We received your request to book {room['name']} on "
        f"{booking['start_time'].strftime('%A, %d %B %Y')} at {booking['start_time'].strftime('%H:%M')}.\n\n"
        f"This booking needs admin approval "
        f"({'private event' if booking['is_private_event'] else 'more than 2 weeks in advance'}). "
        f"We'll let you know as soon as it's reviewed."
    )
    await asyncio.gather(send_email(booking["email"], subject, body), send_whatsapp(booking["phone"], body))


async def notify_booking_decision(booking: dict, room: dict, approved: bool):
    if approved:
        await notify_booking_confirmed(booking, room)
        return
    subject = f"Booking not approved: {room['name']}"
    body = (
        f"Hi {booking['requester_name']},\n\n"
        f"Unfortunately your request to book {room['name']} on "
        f"{booking['start_time'].strftime('%A, %d %B %Y')} was not approved."
    )
    if booking.get("admin_note"):
        body += f"\n\nNote from admin: {booking['admin_note']}"
    body += "\n\nPlease contact the admin office if you'd like to discuss alternatives."
    await asyncio.gather(send_email(booking["email"], subject, body), send_whatsapp(booking["phone"], body))


async def notify_admin_new_request(booking: dict, room: dict):
    subject = f"New booking needs approval: {room['name']}"
    body = (
        f"{booking['requester_name']} ({booking['congregation']}) requested {room['name']} "
        f"on {booking['start_time'].strftime('%d %b %Y, %H:%M')} "
        f"for {booking['headcount']} people.\n"
        f"Reason: {booking['purpose']}\n"
        f"{'This is a private event.' if booking['is_private_event'] else ''}\n\n"
        f"Review it in the admin portal: {settings.frontend_url}/admin/approvals"
    )
    tasks = []
    if settings.admin_notify_email:
        tasks.append(send_email(settings.admin_notify_email, subject, body))
    if settings.admin_notify_whatsapp:
        tasks.append(send_whatsapp(settings.admin_notify_whatsapp, body))
    if tasks:
        await asyncio.gather(*tasks)
