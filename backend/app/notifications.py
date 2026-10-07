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
import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from app.config import settings
from app.date_format import format_day_long, format_day_short, format_time, format_time_range, to_local

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


def esc(value) -> str:
    """HTML-escape anything a person typed before it goes into an email body."""
    return html.escape("" if value is None else str(value), quote=True)


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
        f'<td style="padding:6px 0;color:{BRAND["ink_soft"]};font-size:13px;width:140px;vertical-align:top;">{esc(label)}</td>'
        f'<td style="padding:6px 0;color:{BRAND["ink"]};font-size:14px;font-weight:600;">{esc(value)}</td>'
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
            f'<strong style="color:{BRAND["ink"]};">Please leave the room like this:</strong><br>{esc(setup_notes).replace(chr(10), "<br>")}</p>'
        )
    if room.get("booking_message"):
        parts.append(
            f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:16px 0 0;">{esc(room["booking_message"]).replace(chr(10), "<br>")}</p>'
        )
    return "".join(parts)


def _email_shell(
    heading: str,
    intro: str,
    content_html: str,
    badge_html: str = "",
    preheader: str = "",
    brand: str = "Pinehurst Campus",
    subtitle: str = "Room Booking System",
    footer: str = "Questions about this booking? Contact the admin office.",
) -> str:
    # heading / intro / content_html are HTML the caller has already escaped
    # where they embed user data; brand, subtitle, footer and preheader are
    # plain text and escaped here.
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin:0;padding:0;background:{BRAND['bg']};font-family:{BODY_FONT};">
<span style="display:none;font-size:1px;color:{BRAND['bg']};line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">{esc(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BRAND['bg']};padding:32px 16px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(35,40,35,0.08);">
<tr>
<td style="background:{BRAND['teal']};padding:28px 32px;">
<div style="font-family:{DISPLAY_FONT};font-size:22px;font-weight:700;color:#ffffff;letter-spacing:.01em;">{esc(brand)}</div>
<div style="font-size:13px;color:{BRAND['teal_tint']};margin-top:4px;">{esc(subtitle)}</div>
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
{esc(brand)} &middot; {esc(subtitle)}<br>
{esc(footer)}
</p>
</td>
</tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _email_credentials() -> tuple[str, str]:
    """
    The sender address and App Password exactly as Gmail needs them. Values
    pasted into a hosting dashboard often pick up a trailing space or newline,
    and Google shows App Passwords in four groups with spaces between — both
    would otherwise fail the login with an unhelpful "authentication" error.
    """
    sender = "".join(settings.email_from.split())
    password = "".join(settings.email_password.split())
    return sender, password


def email_is_configured() -> bool:
    sender, password = _email_credentials()
    return bool(sender and password)


def _send_email_sync(to: str, subject: str, text_body: str, html_body: str | None) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = " ".join(subject.split())
    sender, password = _email_credentials()
    from_name = settings.email_from_name.strip()
    msg["From"] = f"{from_name} <{sender}>" if from_name else sender
    msg["To"] = to
    # Attach the plain-text part first, HTML last — for "alternative" MIME,
    # clients render the last part they understand, so HTML wins where
    # supported and plain text remains the fallback everywhere else.
    msg.attach(MIMEText(text_body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, [to], msg.as_string())


async def send_email(to: str, subject: str, text_body: str, html_body: str | None = None):
    if not email_is_configured():
        print(f"[email skipped - no EMAIL_FROM/EMAIL_PASSWORD] to={to} subject={subject}", flush=True)
        return
    try:
        # smtplib is blocking — running it directly in an async function
        # would stall the whole event loop (every other concurrent request)
        # for the round-trip. Push it to a thread instead.
        await asyncio.to_thread(_send_email_sync, to, subject, text_body, html_body)
        print(f"[email sent] to={to} subject={subject}", flush=True)
    except Exception as e:
        print(f"[email error] to={to} {type(e).__name__}: {e}", flush=True)


async def send_whatsapp(to_phone: str, message: str):
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        print(f"[whatsapp skipped - no credentials] to={to_phone} message={message}", flush=True)
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
                print(f"[whatsapp error] {resp.status_code} {resp.text}", flush=True)
    except Exception as e:
        print(f"[whatsapp error] {e}", flush=True)


PRIVATE_BRAND = "Joshua Generation Pinehurst"
CHURCH_BRAND = "Pinehurst"

# What the booker must know about a private (non-congregation) venue booking.
PRIVATE_RESPONSIBILITIES = [
    "You are responsible for organising your own sound team/operator where sound or AV equipment will be used.",
    "You are responsible for arranging appropriate security for the event/night.",
    "You are responsible for ensuring the venue is properly locked up after the event.",
    "All doors and windows must be checked and secured before leaving.",
    "The alarm must be armed according to the instructions provided.",
    "All keys, remotes and items used during the event must be returned to the place where they were found.",
    "The venue, rooms, bathrooms, equipment and facilities must be left in the condition in which they were found.",
    "All rubbish, leftover food and drinks, décor and other items brought into the venue must be removed after the event.",
    "You accept responsibility for any loss, breakage or damage to the venue or church property during your booking.",
    "There is a strict no alcohol and no smoking policy.",
    "No Prestik may be used on walls, fixtures may not be removed, and no confetti or petals may be used indoors.",
]
PRIVATE_TABLECLOTH_NOTE = "If church tablecloths are used, they must be cleaned and returned to the church in good condition."
PRIVATE_ACCESS_NOTE = "Your gate access code, alarm code and final access/lock-up instructions will be sent to you the day before your event."

CHURCH_REMINDERS = [
    "Please organise a suitable sound/AV operator if you are using the venue systems.",
    "Please ensure appropriate security arrangements are in place where required.",
    "Leave all rooms and facilities clean and in the condition in which they were found.",
    "Remove all food, rubbish, décor and equipment brought in for the event.",
    "Return all keys, remotes and items to where they were found.",
    "Ensure all doors and windows are properly locked before leaving.",
    "Ensure the venue is correctly alarmed and secured when leaving.",
    "Report any breakages, damage or problems to Admin.",
]
CHURCH_ACCESS_NOTE = "The gate code, alarm code and any final access instructions will be sent to you the day before your event."

# Event type -> how far ahead the church may cancel. Keyed on the booking's
# purpose (what the booker picked as the event type), compared case-insensitively.
CANCELLATION_NOTICES = {
    "wedding": "Please note that Joshua Generation Pinehurst reserves the right to cancel a wedding venue booking up to three months before the event date.",
    "birthday": "Please note that Joshua Generation Pinehurst reserves the right to cancel a birthday venue booking up to two months before the event date.",
}


def _event_type(booking: dict) -> str:
    return (booking.get("purpose") or "").strip()


def _event_name(booking: dict) -> str:
    """Bookings have no separate event-name field: use what the booker described under "Other", else the event type."""
    if _event_type(booking).lower() == "other" and (booking.get("purpose_other") or "").strip():
        return booking["purpose_other"].strip()
    return _event_type(booking) or "Your event"


def _cancellation_notice(booking: dict) -> str | None:
    return CANCELLATION_NOTICES.get(_event_type(booking).lower())


def _reference(booking: dict) -> str | None:
    """A short booking reference taken from the stored id, when there is one."""
    raw = booking.get("_id") or booking.get("id")
    return f"JGP-{str(raw)[-8:].upper()}" if raw else None


def _local_times(booking: dict):
    return to_local(booking["start_time"]), to_local(booking["end_time"])


def _bullets_html(items: list[str]) -> str:
    lis = "".join(f'<li style="margin:0 0 7px;">{esc(item)}</li>' for item in items)
    return (
        f'<ul style="margin:10px 0 0;padding-left:20px;font-size:14px;line-height:1.55;color:{BRAND["ink"]};">{lis}</ul>'
    )


def _section_heading_html(text: str) -> str:
    return (
        f'<h2 style="font-family:{DISPLAY_FONT};font-size:16px;color:{BRAND["ink"]};margin:26px 0 0;'
        f'font-weight:700;">{esc(text)}</h2>'
    )


def _paragraph_html(text: str, emphasis: bool = False) -> str:
    box = (
        f"background:{BRAND['amber_tint']};border-radius:8px;padding:12px 14px;color:{BRAND['ink']};"
        if emphasis
        else f"color:{BRAND['ink_soft']};"
    )
    return f'<p style="font-size:14px;line-height:1.6;margin:16px 0 0;{box}">{esc(text)}</p>'


def _confirmation_details(booking: dict, room: dict) -> list[tuple[str, str]]:
    start, end = _local_times(booking)
    rows = [
        ("Event", _event_name(booking)),
        ("Date", format_day_long(start)),
        ("Time", format_time_range(start, end)),
        ("Venue/Room", room["name"]),
    ]
    # Straight from Manage Rooms: whatever equipment the admin ticked for this
    # room (chairs, sound system, AV...) and where to find it.
    amenities = [a for a in (room.get("amenities") or []) if a]
    if amenities:
        rows.append(("Room equipment", ", ".join(amenities)))
    if room.get("location"):
        rows.append(("Location", room["location"]))
    if _reference(booking):
        rows.append(("Reference", _reference(booking)))
    return rows


def _details_text(rows: list[tuple[str, str]]) -> str:
    return "\n".join(f"{label}: {value}" for label, value in rows)


def _room_notes_text(room: dict) -> str:
    return _room_setup_block(room["name"], room.get("setup_notes")) + _room_message_block(room)


def build_confirmation_email(booking: dict, room: dict) -> tuple[str, str, str]:
    """
    Returns (subject, plain_text, html) for a booking that has just been
    approved. Private bookings (weddings, birthdays, other non-congregation
    events) get the fuller conditions; church bookings get a shorter set of
    reminders. Neither contains gate or alarm codes — those go out the day
    before the event.
    """
    private = bool(booking.get("is_private_event"))
    event = _event_name(booking)
    name = booking["requester_name"]
    rows = _confirmation_details(booking, room)
    details_text = _details_text(rows)

    if private:
        brand, subtitle = PRIVATE_BRAND, "Venue booking"
        subject = f"Booking Confirmed – {event} | Joshua Generation Pinehurst"
        intro_text = f"This email confirms your booking for {event} at Joshua Generation Pinehurst."
        reminders_heading = "Important Information"
        reminders = PRIVATE_RESPONSIBILITIES
        extra_notes = [PRIVATE_TABLECLOTH_NOTE]
        access_note = PRIVATE_ACCESS_NOTE
        cancellation = _cancellation_notice(booking)
        closing = [
            "If you have any questions regarding your booking or venue arrangements, please contact the Pinehurst admin team.",
        ]
        sign_off = "Joshua Generation Pinehurst"
        footer = "Questions about your booking? Contact the Pinehurst admin team."
    else:
        brand, subtitle = CHURCH_BRAND, "Booking confirmation"
        subject = f"Booking Confirmed – {event} | Pinehurst"
        intro_text = f"This email confirms your booking for {event}."
        reminders_heading = "A few reminders for your booking"
        reminders = CHURCH_REMINDERS
        extra_notes = []
        access_note = CHURCH_ACCESS_NOTE
        cancellation = None  # the wedding/birthday clauses never apply to church bookings
        closing = []
        sign_off = "Pinehurst"
        footer = "Questions about your booking? Contact the Pinehurst admin team."

    # ---- plain text
    parts = [f"Dear {name},", "", intro_text, "", "BOOKING DETAILS", details_text]
    notes_text = _room_notes_text(room).strip()
    if notes_text:
        parts += ["", notes_text]
    parts += ["", reminders_heading.upper()] + [f"- {item}" for item in reminders]
    for note in extra_notes:
        parts += ["", note]
    parts += ["", access_note]
    if cancellation:
        parts += ["", cancellation]
    for line in closing:
        parts += ["", line]
    parts += ["", "Kind regards,", sign_off]
    text_body = "\n".join(parts)

    # ---- HTML
    content = _section_heading_html("Booking Details") + _detail_rows_html(rows)
    content += _room_extras_html(room)
    content += _section_heading_html(reminders_heading) + _bullets_html(reminders)
    for note in extra_notes:
        content += _paragraph_html(note)
    content += _paragraph_html(access_note, emphasis=True)
    if cancellation:
        content += _paragraph_html(cancellation)
    for line in closing:
        content += _paragraph_html(line)
    content += (
        f'<p style="font-size:14px;line-height:1.6;margin:22px 0 0;color:{BRAND["ink"]};">'
        f"Kind regards,<br><strong>{esc(sign_off)}</strong></p>"
    )
    html_body = _email_shell(
        heading=f"Dear {esc(name)},",
        intro=esc(intro_text),
        badge_html=_badge_html("Confirmed", BRAND["success"], BRAND["success_tint"]),
        content_html=content,
        preheader=f"Your booking for {event} is confirmed.",
        brand=brand,
        subtitle=subtitle,
        footer=footer,
    )
    return subject, text_body, html_body


async def notify_booking_confirmed(booking: dict, room: dict):
    """
    Sent once a booking is approved (auto-approved, approved by an admin, or
    created by an admin). Email and WhatsApp go out together; a failure in
    either is logged by its sender and never raised, so it can't undo the
    booking.
    """
    subject, text_body, html_body = build_confirmation_email(booking, room)

    # WhatsApp stays short — the full conditions are in the email.
    whatsapp_body = (
        f"Hi {booking['requester_name']}, your booking for {_event_name(booking)} is confirmed.\n\n"
        f"{_details_text(_confirmation_details(booking, room))}\n\n"
        "The full details and venue conditions have been emailed to you."
    )
    await asyncio.gather(
        send_email(booking["email"], subject, text_body, html_body),
        send_whatsapp(booking["phone"], whatsapp_body),
    )


async def notify_booking_pending(booking: dict, room: dict):
    start, end = _local_times(booking)
    subject = f"Booking request received: {room['name']}"
    body = (
        f"Hi {booking['requester_name']},\n\n"
        f"We received your request to book {room['name']} on "
        f"{format_day_long(start)} at {format_time(start)}.\n\n"
        f"This booking needs admin approval "
        f"({'private event' if booking['is_private_event'] else 'more than 2 weeks in advance'}). "
        f"We'll let you know as soon as it's reviewed."
    )
    reason = "it's a private event" if booking["is_private_event"] else "it's more than 2 weeks out"
    html_body = _email_shell(
        heading="We've got your request",
        intro=f"Hi {esc(booking['requester_name'])}, thanks for requesting <strong>{esc(room['name'])}</strong>.",
        badge_html=_badge_html("Awaiting the office", BRAND["amber"], BRAND["amber_tint"]),
        content_html=(
            _detail_rows_html(
                [
                    ("Room", room["name"]),
                    ("Date", format_day_long(start)),
                    ("Time", format_time_range(start, end)),
                ]
            )
            + f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:20px 0 0;">'
            f"This needs admin approval because {reason}. We'll let you know as soon as it's reviewed.</p>"
        ),
    )
    await asyncio.gather(send_email(booking["email"], subject, body, html_body), send_whatsapp(booking["phone"], body))


async def notify_booking_decision(booking: dict, room: dict, approved: bool):
    if approved:
        await notify_booking_confirmed(booking, room)
        return
    start, _ = _local_times(booking)
    subject = f"Booking not approved: {room['name']}"
    body = (
        f"Hi {booking['requester_name']},\n\n"
        f"Unfortunately your request to book {room['name']} on "
        f"{format_day_long(start)} was not approved."
    )
    if booking.get("admin_note"):
        body += f"\n\nNote from admin: {booking['admin_note']}"
    body += "\n\nPlease contact the admin office if you'd like to discuss alternatives."

    note_html = (
        f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:16px 0 0;">'
        f'<strong style="color:{BRAND["ink"]};">Note from admin:</strong><br>{esc(booking["admin_note"])}</p>'
        if booking.get("admin_note")
        else ""
    )
    html_body = _email_shell(
        heading="Booking not approved",
        intro=f"Hi {esc(booking['requester_name'])}, unfortunately your request for <strong>{esc(room['name'])}</strong> wasn't approved.",
        badge_html=_badge_html("Declined", BRAND["danger"], BRAND["danger_tint"]),
        content_html=(
            _detail_rows_html(
                [
                    ("Room", room["name"]),
                    ("Date", format_day_long(start)),
                ]
            )
            + note_html
            + f'<p style="font-size:13px;color:{BRAND["ink_soft"]};line-height:1.6;margin:20px 0 0;">'
            f"Please contact the admin office if you'd like to discuss alternatives.</p>"
        ),
    )
    await asyncio.gather(send_email(booking["email"], subject, body, html_body), send_whatsapp(booking["phone"], body))


async def notify_admin_new_request(booking: dict, room: dict):
    start, _ = _local_times(booking)
    subject = f"New booking needs approval: {room['name']}"
    body = (
        f"{booking['requester_name']} ({booking['congregation']}) requested {room['name']} "
        f"on {format_day_short(start)}, {format_time(start)} "
        f"for {booking['headcount']} people.\n"
        f"Reason: {booking['purpose']}\n"
        f"{'This is a private event.' if booking['is_private_event'] else ''}\n\n"
        f"Review it in the admin portal: {settings.frontend_url}/admin/bookings"
    )
    html_body = _email_shell(
        heading="New booking needs approval",
        intro=f"<strong>{esc(booking['requester_name'])}</strong> ({esc(booking['congregation'])}) requested {esc(room['name'])}.",
        badge_html=_badge_html("Action needed", BRAND["amber"], BRAND["amber_tint"]),
        content_html=(
            _detail_rows_html(
                [
                    ("Room", room["name"]),
                    ("Date", format_day_long(start)),
                    ("Time", format_time(start)),
                    ("Attendance", str(booking["headcount"])),
                    ("Purpose", booking["purpose"]),
                ]
                + ([("Note", "This is a private event.")] if booking["is_private_event"] else [])
            )
            + f'<p style="margin:24px 0 0;"><a href="{esc(settings.frontend_url)}/admin/bookings" '
            f'style="display:inline-block;background:{BRAND["teal"]};color:#ffffff;text-decoration:none;'
            f'padding:10px 20px;border-radius:8px;font-size:14px;font-weight:600;">Review in admin portal</a></p>'
        ),
    )
    tasks = []
    if settings.admin_notify_email:
        tasks.append(send_email(settings.admin_notify_email, subject, body, html_body))
    if settings.admin_notify_whatsapp:
        tasks.append(send_whatsapp(settings.admin_notify_whatsapp, body))
    if tasks:
        await asyncio.gather(*tasks)
