"""
Sends booking confirmations, approval requests, and status updates via
email (the church's own Gmail account, over SMTP) and WhatsApp (Meta Cloud
API).

Meta WhatsApp Cloud API is free at the volume a single church campus will
use: 1,000 free service conversations/month. Gmail SMTP has no per-email
cost but a rough daily send cap (~500/day on a regular Gmail account,
~2,000/day on Google Workspace) — plenty for this volume.

If credentials are not set in .env, calls are skipped and logged instead of
raising errors, so the booking flow still works during setup/testing.

Emails are sent as HTML (branded to match the frontend's teal/amber look,
using web-safe font stacks since email clients don't reliably load web
fonts) with a plain-text fallback for clients/spam filters that prefer it.
"""
import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from app.config import settings
from app.date_format import format_day_long, format_day_short, format_time, format_time_range

BRAND = {
    "teal": "#1B3A6C",
    "teal_dark": "#12294D",
    "teal_tint": "#E7ECF6",
    "amber": "#C98A2C",
    "amber_tint": "#FBF0DE",
    "danger": "#B5453A",
    "danger_tint": "#FBEAE8",
    "success": "#3F7A5C",
    "success_tint": "#E7F2EC",
    "bg": "#F5F6F2",
    "surface_sunken": "#ECEEE8",
    "ink": "#232823",
    "ink_soft": "#5B6259",
    "border": "#DDE1D8",
}

DISPLAY_FONT = "Georgia,'Times New Roman',serif"
BODY_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


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


def _badge_html(label: str, color: str, tint: str) -> str:
    return (
        f'<span style="display:inline-block;padding:4px 12px;border-radius:999px;'
        f'background:{tint};color:{color};font-size:12px;font-weight:700;'
        f'letter-spacing:.02em;text-transform:uppercase;">{label}</span>'
    )


def _detail_rows_html(pairs: list[tuple[str, str]]) -> str:
    rows = "".join(
        f'<tr>'
        f'<td style="padding:6px 0;color:{BRAND["ink_soft"]};font-size:13px;width:140px;vertical-align:top;">{label}</td>'
        f'<td style="padding:6px 0;color:{BRAND["ink"]};font-size:14px;font-weight:600;">{value}</td>'
        f'</tr>'
        for label, value in pairs
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">{rows}</table>'


def _room_extras_html(room: dict) -> str:
    parts = []
    setup_notes = room.get("setup_notes")
    if setup_notes:
        parts.append(
            f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:16px 0 0;">'
            f'<strong style="color:{BRAND["ink"]};">Please leave the room like this:</strong><br>{setup_notes}</p>'
        )
    if room.get("booking_message"):
        parts.append(
            f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:16px 0 0;">{room["booking_message"]}</p>'
        )
    return "".join(parts)


def _email_shell(heading: str, intro: str, content_html: str, badge_html: str = "", preheader: str = "") -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin:0;padding:0;background:{BRAND['bg']};font-family:{BODY_FONT};">
<span style="display:none;font-size:1px;color:{BRAND['bg']};line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">{preheader}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BRAND['bg']};padding:32px 16px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(35,40,35,0.08);">
<tr>
<td style="background:{BRAND['teal']};padding:28px 32px;">
<div style="font-family:{DISPLAY_FONT};font-size:22px;font-weight:700;color:#ffffff;letter-spacing:.01em;">Pinehurst Campus</div>
<div style="font-size:13px;color:{BRAND['teal_tint']};margin-top:4px;">Room Booking System</div>
</td>
</tr>
<tr>
<td style="padding:32px;">
{f'<div style="margin-bottom:14px;">{badge_html}</div>' if badge_html else ''}
<h1 style="font-family:{DISPLAY_FONT};font-size:20px;color:{BRAND['ink']};margin:0 0 12px;font-weight:700;">{heading}</h1>
<p style="font-size:14px;color:{BRAND['ink_soft']};line-height:1.6;margin:0;">{intro}</p>
{content_html}
</td>
</tr>
<tr>
<td style="background:{BRAND['surface_sunken']};padding:20px 32px;border-top:1px solid {BRAND['border']};">
<p style="font-size:12px;color:{BRAND['ink_soft']};margin:0;line-height:1.6;">
Pinehurst Campus &middot; Room Booking System<br>
Questions about this booking? Contact the admin office.
</p>
</td>
</tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _send_email_sync(to: str, subject: str, text_body: str, html_body: str | None) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.email_from}>" if settings.email_from_name else settings.email_from
    msg["To"] = to
    # Attach the plain-text part first, HTML last — for "alternative" MIME,
    # clients render the last part they understand, so HTML wins where
    # supported and plain text remains the fallback everywhere else.
    msg.attach(MIMEText(text_body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        server.starttls()
        server.login(settings.email_from, settings.email_password)
        server.sendmail(settings.email_from, [to], msg.as_string())


async def send_email(to: str, subject: str, text_body: str, html_body: str | None = None):
    if not settings.email_from or not settings.email_password:
        print(f"[email skipped - no EMAIL_FROM/EMAIL_PASSWORD] to={to} subject={subject}")
        return
    try:
        # smtplib is blocking — running it directly in an async function
        # would stall the whole event loop (every other concurrent request)
        # for the round-trip. Push it to a thread instead.
        await asyncio.to_thread(_send_email_sync, to, subject, text_body, html_body)
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
    subject = f"Booking confirmed: {room['name']} on {format_day_short(booking['start_time'])}, {format_time(booking['start_time'])}"
    body = (
        f"Hi {booking['requester_name']},\n\n"
        f"Your booking for {room['name']} is confirmed.\n\n"
        f"Date: {format_day_long(booking['start_time'])}\n"
        f"Time: {format_time_range(booking['start_time'], booking['end_time'])}\n"
        f"Expected attendance: {booking['headcount']}\n"
        f"Purpose: {booking['purpose']}"
        f"{_room_setup_block(room['name'], room.get('setup_notes'))}"
        f"{_room_message_block(room)}\n\n"
        f"If you need to change or cancel this booking, contact the admin office."
    )
    html = _email_shell(
        heading="Your booking is confirmed",
        intro=f"Hi {booking['requester_name']}, your booking for <strong>{room['name']}</strong> is all set.",
        badge_html=_badge_html("Confirmed", BRAND["success"], BRAND["success_tint"]),
        content_html=(
            _detail_rows_html(
                [
                    ("Room", room["name"]),
                    ("Date", format_day_long(booking["start_time"])),
                    ("Time", format_time_range(booking["start_time"], booking["end_time"])),
                    ("Attendance", str(booking["headcount"])),
                    ("Purpose", booking["purpose"]),
                ]
            )
            + _room_extras_html(room)
            + f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:20px 0 0;">'
            f"Need to change or cancel this booking? Contact the admin office.</p>"
        ),
    )
    await asyncio.gather(send_email(booking["email"], subject, body, html), send_whatsapp(booking["phone"], body))


async def notify_booking_pending(booking: dict, room: dict):
    subject = f"Booking request received: {room['name']}"
    body = (
        f"Hi {booking['requester_name']},\n\n"
        f"We received your request to book {room['name']} on "
        f"{format_day_long(booking['start_time'])} at {format_time(booking['start_time'])}.\n\n"
        f"This booking needs admin approval "
        f"({'private event' if booking['is_private_event'] else 'more than 2 weeks in advance'}). "
        f"We'll let you know as soon as it's reviewed."
    )
    reason = "it's a private event" if booking["is_private_event"] else "it's more than 2 weeks out"
    html = _email_shell(
        heading="We've got your request",
        intro=f"Hi {booking['requester_name']}, thanks for requesting <strong>{room['name']}</strong>.",
        badge_html=_badge_html("Pending approval", BRAND["amber"], BRAND["amber_tint"]),
        content_html=(
            _detail_rows_html(
                [
                    ("Room", room["name"]),
                    ("Date", format_day_long(booking["start_time"])),
                    ("Time", format_time_range(booking["start_time"], booking["end_time"])),
                ]
            )
            + f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:20px 0 0;">'
            f"This needs admin approval because {reason}. We'll let you know as soon as it's reviewed.</p>"
        ),
    )
    await asyncio.gather(send_email(booking["email"], subject, body, html), send_whatsapp(booking["phone"], body))


async def notify_booking_decision(booking: dict, room: dict, approved: bool):
    if approved:
        await notify_booking_confirmed(booking, room)
        return
    subject = f"Booking not approved: {room['name']}"
    body = (
        f"Hi {booking['requester_name']},\n\n"
        f"Unfortunately your request to book {room['name']} on "
        f"{format_day_long(booking['start_time'])} was not approved."
    )
    if booking.get("admin_note"):
        body += f"\n\nNote from admin: {booking['admin_note']}"
    body += "\n\nPlease contact the admin office if you'd like to discuss alternatives."

    note_html = (
        f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:16px 0 0;">'
        f'<strong style="color:{BRAND["ink"]};">Note from admin:</strong><br>{booking["admin_note"]}</p>'
        if booking.get("admin_note")
        else ""
    )
    html = _email_shell(
        heading="Booking not approved",
        intro=f"Hi {booking['requester_name']}, unfortunately your request for <strong>{room['name']}</strong> wasn't approved.",
        badge_html=_badge_html("Not approved", BRAND["danger"], BRAND["danger_tint"]),
        content_html=(
            _detail_rows_html(
                [
                    ("Room", room["name"]),
                    ("Date", format_day_long(booking["start_time"])),
                ]
            )
            + note_html
            + f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:20px 0 0;">'
            f"Please contact the admin office if you'd like to discuss alternatives.</p>"
        ),
    )
    await asyncio.gather(send_email(booking["email"], subject, body, html), send_whatsapp(booking["phone"], body))


async def notify_admin_new_request(booking: dict, room: dict):
    subject = f"New booking needs approval: {room['name']}"
    body = (
        f"{booking['requester_name']} ({booking['congregation']}) requested {room['name']} "
        f"on {format_day_short(booking['start_time'])}, {format_time(booking['start_time'])} "
        f"for {booking['headcount']} people.\n"
        f"Reason: {booking['purpose']}\n"
        f"{'This is a private event.' if booking['is_private_event'] else ''}\n\n"
        f"Review it in the admin portal: {settings.frontend_url}/admin/approvals"
    )
    html = _email_shell(
        heading="New booking needs approval",
        intro=f"<strong>{booking['requester_name']}</strong> ({booking['congregation']}) requested {room['name']}.",
        badge_html=_badge_html("Action needed", BRAND["amber"], BRAND["amber_tint"]),
        content_html=(
            _detail_rows_html(
                [
                    ("Room", room["name"]),
                    ("Date", format_day_long(booking["start_time"])),
                    ("Time", format_time(booking["start_time"])),
                    ("Attendance", str(booking["headcount"])),
                    ("Purpose", booking["purpose"]),
                ]
                + ([("Note", "This is a private event.")] if booking["is_private_event"] else [])
            )
            + f'<p style="margin:24px 0 0;"><a href="{settings.frontend_url}/admin/approvals" '
            f'style="display:inline-block;background:{BRAND["teal"]};color:#ffffff;text-decoration:none;'
            f'padding:10px 20px;border-radius:8px;font-size:14px;font-weight:600;">Review in admin portal</a></p>'
        ),
    )
    tasks = []
    if settings.admin_notify_email:
        tasks.append(send_email(settings.admin_notify_email, subject, body, html))
    if settings.admin_notify_whatsapp:
        tasks.append(send_whatsapp(settings.admin_notify_whatsapp, body))
    if tasks:
        await asyncio.gather(*tasks)
