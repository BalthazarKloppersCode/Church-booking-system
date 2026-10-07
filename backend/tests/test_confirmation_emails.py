import email as email_lib
import re
from datetime import datetime

import pytest
from bson import ObjectId

from app import notifications, whatsapp
from app.config import settings
from app.notifications import build_confirmation_email, notify_booking_confirmed

ROOM = {"name": "Training Hall", "setup_notes": None, "booking_message": None}

WEDDING_CLAUSE = "reserves the right to cancel a wedding venue booking up to three months before the event date"
BIRTHDAY_CLAUSE = "reserves the right to cancel a birthday venue booking up to two months before the event date"


def make_booking(**overrides):
    booking = {
        "_id": ObjectId("65a1b2c3d4e5f60718293a4b"),
        "requester_name": "Jane Doe",
        "congregation": "Brackenfell",
        "email": "jane@example.com",
        "phone": "+27820000000",
        "headcount": 80,
        # Stored as naive UTC: 08:00-10:00 UTC is 10:00-12:00 in Johannesburg.
        "start_time": datetime(2026, 10, 14, 8, 0),
        "end_time": datetime(2026, 10, 14, 10, 0),
        "purpose": "Wedding",
        "purpose_other": None,
        "is_private_event": True,
    }
    booking.update(overrides)
    return booking


def test_private_wedding_email_content():
    subject, text, html = build_confirmation_email(make_booking(), ROOM)

    assert subject == "Booking Confirmed – Wedding | Joshua Generation Pinehurst"
    assert text.startswith("Dear Jane Doe,\n\nThis email confirms your booking for Wedding at Joshua Generation Pinehurst.")
    for expected in (
        "Event: Wedding",
        "Date: Wednesday 14 October 2026",
        "Venue/Room: Training Hall",
        "IMPORTANT INFORMATION",
        "strict no alcohol and no smoking policy",
        "No Prestik may be used on walls",
        "church tablecloths are used",
        "Your gate access code, alarm code and final access/lock-up instructions will be sent to you the day before your event.",
        "please contact the Pinehurst admin team.",
        "Kind regards,\nJoshua Generation Pinehurst",
    ):
        assert expected in text, expected
    for sentence in (
        "This email confirms your booking for Wedding at Joshua Generation Pinehurst.",
        "strict no alcohol and no smoking policy.",
        "No Prestik may be used on walls",
        "church tablecloths are used",
        "will be sent to you the day before your event.",
        "Important Information",
        "Booking Details",
    ):
        assert sentence in html, sentence
    assert WEDDING_CLAUSE in text
    assert BIRTHDAY_CLAUSE not in text
    assert WEDDING_CLAUSE in html


def test_times_are_shown_in_church_local_time_not_utc():
    _, text, _ = build_confirmation_email(make_booking(), ROOM)
    assert "Time: 10:00–12:00" in text
    assert "08:00" not in text


def test_birthday_gets_the_two_month_notice_only():
    subject, text, html = build_confirmation_email(make_booking(purpose="Birthday"), ROOM)
    assert subject.startswith("Booking Confirmed – Birthday")
    assert BIRTHDAY_CLAUSE in text and BIRTHDAY_CLAUSE in html
    assert WEDDING_CLAUSE not in text and "three months" not in text


@pytest.mark.parametrize("purpose", ["Funeral / memorial", "Conference / seminar", "Other"])
def test_other_private_events_get_no_cancellation_clause(purpose):
    _, text, html = build_confirmation_email(make_booking(purpose=purpose, purpose_other="Reunion"), ROOM)
    assert "reserves the right to cancel" not in text
    assert "reserves the right to cancel" not in html
    # still the private template
    assert "IMPORTANT INFORMATION" in text


def test_event_name_uses_the_description_for_other():
    subject, text, _ = build_confirmation_email(make_booking(purpose="Other", purpose_other="Smith family reunion"), ROOM)
    assert subject == "Booking Confirmed – Smith family reunion | Joshua Generation Pinehurst"
    assert "Event: Smith family reunion" in text


def test_church_email_is_shorter_and_has_no_cancellation_clauses():
    # Even a birthday/wedding purpose must not pull the clauses into the church template.
    for purpose in ("Kids ministry", "Birthday", "Wedding"):
        subject, text, html = build_confirmation_email(
            make_booking(is_private_event=False, purpose=purpose), ROOM
        )
        assert subject == f"Booking Confirmed – {purpose} | Pinehurst"
        assert text.startswith(f"Dear Jane Doe,\n\nThis email confirms your booking for {purpose}.\n")
        assert "A FEW REMINDERS FOR YOUR BOOKING" in text
        assert "Report any breakages, damage or problems to Admin." in text
        assert "The gate code, alarm code and any final access instructions will be sent to you the day before your event." in text
        assert "reserves the right to cancel" not in text and "reserves the right to cancel" not in html
        assert "Prestik" not in text and "tablecloths" not in text  # the contractual private-only items

    _, private_text, _ = build_confirmation_email(make_booking(), ROOM)
    _, church_text, _ = build_confirmation_email(make_booking(is_private_event=False), ROOM)
    assert len(church_text) < len(private_text)


def test_no_access_codes_in_either_email():
    for private in (True, False):
        _, text, html = build_confirmation_email(make_booking(is_private_event=private), ROOM)
        for body in (text, html):
            assert not re.search(r"(gate|alarm)\s+code\s*(is|:)\s*\w*\d", body, re.I)


def test_user_supplied_values_are_html_escaped():
    booking = make_booking(
        requester_name="<script>alert(1)</script>",
        purpose="Other",
        purpose_other="Tom & Jerry <b>party</b>",
    )
    room = {"name": "Hall <i>1</i>", "setup_notes": "Wipe <u>tables</u>", "booking_message": "Bring <script>x</script>"}
    _, _, html = build_confirmation_email(booking, room)
    assert "<script>" not in html
    assert "<b>party</b>" not in html and "<i>1</i>" not in html and "<u>tables</u>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Tom &amp; Jerry &lt;b&gt;party&lt;/b&gt;" in html


def test_booking_reference_comes_from_the_stored_id():
    _, text, _ = build_confirmation_email(make_booking(), ROOM)
    assert "Reference: JGP-18293A4B" in text
    _, text, _ = build_confirmation_email(make_booking(_id=None), ROOM)
    assert "Reference" not in text


def test_room_specific_notes_are_kept_when_the_room_has_them():
    room = {"name": "Coffee Shop", "setup_notes": "Chairs stacked", "booking_message": "Bring your own milk"}
    _, text, html = build_confirmation_email(make_booking(is_private_event=False), room)
    assert "Chairs stacked" in text and "Bring your own milk" in text
    assert "Chairs stacked" in html


class _FakeSMTP:
    sent = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, *args):
        pass

    def sendmail(self, sender, recipients, message):
        _FakeSMTP.sent.append((sender, recipients, message))


async def test_subject_cannot_inject_extra_headers(monkeypatch):
    _FakeSMTP.sent = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(settings, "email_from", "church@example.com")
    monkeypatch.setattr(settings, "email_password", "app-password")
    monkeypatch.setattr(settings, "whatsapp_access_token", "")

    booking = make_booking(purpose="Other", purpose_other="Party\r\nBcc: attacker@example.com")
    await notify_booking_confirmed(booking, ROOM)

    assert len(_FakeSMTP.sent) == 1
    sender, recipients, raw = _FakeSMTP.sent[0]
    assert recipients == ["jane@example.com"]
    parsed = email_lib.message_from_string(raw)
    assert parsed["Bcc"] is None
    assert "\n" not in parsed["Subject"] and "\r" not in parsed["Subject"]
    # multipart/alternative: plain text first, HTML last
    kinds = [part.get_content_type() for part in parsed.get_payload()]
    assert kinds == ["text/plain", "text/html"]


async def test_a_failing_email_send_never_raises(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("smtp is down")

    monkeypatch.setattr(notifications, "_send_email_sync", boom)
    monkeypatch.setattr(settings, "email_from", "church@example.com")
    monkeypatch.setattr(settings, "email_password", "app-password")
    monkeypatch.setattr(settings, "whatsapp_access_token", "")

    await notify_booking_confirmed(make_booking(), ROOM)  # must complete without raising


async def test_whatsapp_confirmation_stays_short(monkeypatch):
    sent = []

    async def fake_whatsapp(phone, template, params):
        sent.append((phone, template, params))

    async def fake_email(*args, **kwargs):
        pass

    monkeypatch.setattr(notifications, "send_whatsapp", fake_whatsapp)
    monkeypatch.setattr(notifications, "send_email", fake_email)
    await notify_booking_confirmed(make_booking(), ROOM)

    phone, template, params = sent[0]
    assert phone == "+27820000000"
    assert template == "booking_confirmed"
    message = whatsapp.render(template, params)
    assert "confirmed" in message and "/my-bookings" in message
    assert "Prestik" not in message
    assert len(params) == 7


def test_room_equipment_and_location_come_from_manage_rooms():
    room = {
        "name": "Training Hall",
        "amenities": ["Chairs", "Sound system", "AV"],
        "location": "Upper floor",
        "setup_notes": None,
        "booking_message": None,
    }
    for private in (True, False):
        _, text, html = build_confirmation_email(make_booking(is_private_event=private), room)
        assert "Room equipment: Chairs, Sound system, AV" in text
        assert "Location: Upper floor" in text
        assert "Chairs, Sound system, AV" in html


def test_equipment_rows_are_omitted_when_the_room_lists_none():
    _, text, _ = build_confirmation_email(make_booking(), {"name": "Training Hall", "amenities": [], "location": None})
    assert "Room equipment" not in text and "Location:" not in text


def test_room_equipment_is_html_escaped():
    room = {"name": "Hall", "amenities": ["<b>AV</b>"], "location": None}
    _, _, html = build_confirmation_email(make_booking(), room)
    assert "<b>AV</b>" not in html and "&lt;b&gt;AV&lt;/b&gt;" in html


class _RecordingSMTP(_FakeSMTP):
    logins = []

    def login(self, *args):
        _RecordingSMTP.logins.append(args)


async def test_credentials_with_stray_whitespace_still_log_in(monkeypatch):
    # What a hosting dashboard / Google's grouped App Password display can produce.
    _RecordingSMTP.logins = []
    _FakeSMTP.sent = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", _RecordingSMTP)
    monkeypatch.setattr(settings, "email_from", "  church@gmail.com \n")
    monkeypatch.setattr(settings, "email_password", "abcd efgh ijkl mnop\n")
    monkeypatch.setattr(settings, "email_from_name", "Pinehurst Campus Bookings")
    monkeypatch.setattr(settings, "whatsapp_access_token", "")

    await notifications.send_email("jane@example.com", "Hello", "body")

    assert _RecordingSMTP.logins == [("church@gmail.com", "abcdefghijklmnop")]
    sender, _, raw = _FakeSMTP.sent[0]
    assert sender == "church@gmail.com"
    assert email_lib.message_from_string(raw)["From"] == "Pinehurst Campus Bookings <church@gmail.com>"


async def test_email_is_skipped_not_attempted_without_credentials(monkeypatch, capsys):
    _FakeSMTP.sent = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(settings, "email_from", "church@gmail.com")
    monkeypatch.setattr(settings, "email_password", "   ")
    await notifications.send_email("jane@example.com", "Hello", "body")
    assert _FakeSMTP.sent == []
    assert "[email skipped" in capsys.readouterr().out


async def test_send_results_are_logged_for_the_hosting_logs(monkeypatch, capsys):
    monkeypatch.setattr(notifications.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(settings, "email_from", "church@gmail.com")
    monkeypatch.setattr(settings, "email_password", "abcdefghijklmnop")
    await notifications.send_email("jane@example.com", "Hello", "body")
    assert "[email sent] to=jane@example.com" in capsys.readouterr().out

    monkeypatch.setattr(notifications, "_send_email_sync", lambda *a: (_ for _ in ()).throw(OSError("smtp is down")))
    await notifications.send_email("jane@example.com", "Hello", "body")
    assert "[email error] to=jane@example.com OSError: smtp is down" in capsys.readouterr().out


async def test_every_notification_builds_and_sends(monkeypatch):
    """A bug inside any notify_* would otherwise be swallowed silently by the background task."""
    emails, whatsapps = [], []

    async def fake_email(to, subject, text, html=None):
        emails.append((to, subject))

    async def fake_whatsapp(phone, template, params):
        whatsapps.append(phone)
        # Every template must be real and be given exactly the variables it declares.
        assert template in whatsapp.TEMPLATES
        assert len(params) == len(set(re.findall(r"\{\{(\d+)\}\}", whatsapp.TEMPLATES[template][1])))
        whatsapp.render(template, params)

    monkeypatch.setattr(notifications, "send_email", fake_email)
    monkeypatch.setattr(notifications, "send_whatsapp", fake_whatsapp)
    monkeypatch.setattr(settings, "admin_notify_email", "office@example.com")
    monkeypatch.setattr(settings, "admin_notify_whatsapp", "+27821111111")

    booking = make_booking(congregation="Durbanville <b>", admin_note="Clashes with <i>Youth</i>")
    church = make_booking(is_private_event=False, purpose="Kids ministry")

    await notifications.notify_booking_pending(booking, ROOM)
    await notifications.notify_booking_pending(church, ROOM)
    await notifications.notify_booking_decision(booking, ROOM, approved=True)
    await notifications.notify_booking_decision(booking, ROOM, approved=False)
    await notifications.notify_admin_new_request(booking, ROOM)
    await notifications.notify_booking_confirmed(church, ROOM)

    subjects = [s for _, s in emails]
    assert any(s.startswith("Booking request received") for s in subjects)
    assert any(s.startswith("Booking not approved") for s in subjects)
    assert any(s.startswith("New booking needs approval") for s in subjects)
    assert ("office@example.com", "New booking needs approval: Training Hall") in emails
    assert sum(1 for s in subjects if s.startswith("Booking Confirmed")) == 2  # private (via approve) + church
    assert "+27821111111" in whatsapps


def _decoded_subject(raw_message: str) -> str:
    from email.header import decode_header, make_header

    return str(make_header(decode_header(email_lib.message_from_string(raw_message)["Subject"])))


async def test_confirmation_goes_to_the_email_saved_on_the_booking(
    client, rooms_col, bookings_col, booker_headers, auto_approve_congregation, monkeypatch
):
    """Through the real API: the booker is logged in as booker@example.com but books with another contact address."""
    from tests.conftest import booking_payload, make_room

    _FakeSMTP.sent = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(settings, "email_from", "church@gmail.com")
    monkeypatch.setattr(settings, "email_password", "abcdefghijklmnop")
    monkeypatch.setattr(settings, "whatsapp_access_token", "")

    room_id = await make_room(rooms_col, name="Kids Classroom 1", amenities=["Chairs", "TV & HDMI"])
    resp = await client.post(
        "/api/bookings",
        json=booking_payload(
            room_id,
            congregation=auto_approve_congregation,
            start_offset_days=3,
            email="guest@example.com",
            requester_name="Guest Booker",
        ),
        headers=booker_headers,
    )
    assert resp.status_code == 200 and resp.json()["status"] == "approved"

    stored = await bookings_col.find_one({"email": "guest@example.com"})
    assert stored is not None and stored["requester_name"] == "Guest Booker"

    # Auto-approved: exactly one confirmation, addressed to the saved booking email only.
    assert [recipients for _, recipients, _ in _FakeSMTP.sent] == [["guest@example.com"]]
    parsed = email_lib.message_from_string(_FakeSMTP.sent[0][2])
    assert parsed["To"] == "guest@example.com"
    assert _decoded_subject(_FakeSMTP.sent[0][2]).startswith("Booking Confirmed – ")
    body = parsed.get_payload()[0].get_payload(decode=True).decode()
    assert body.startswith("Dear Guest Booker,")
    assert "Room equipment: Chairs, TV & HDMI" in body  # pulled from the room record


async def test_admin_approval_emails_the_booking_email_not_the_admin(
    client, rooms_col, booker_headers, monkeypatch
):
    from tests.conftest import booking_payload, make_room

    _FakeSMTP.sent = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(settings, "email_from", "church@gmail.com")
    monkeypatch.setattr(settings, "email_password", "abcdefghijklmnop")
    monkeypatch.setattr(settings, "whatsapp_access_token", "")
    monkeypatch.setattr(settings, "admin_notify_email", "")

    await client.post(
        "/api/admin/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "hunter22", "setup_secret": settings.admin_setup_secret},
    )
    login = await client.post("/api/admin/login", json={"email": "alice@example.com", "password": "hunter22"})
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    room_id = await make_room(rooms_col)
    created = await client.post(
        "/api/bookings",
        json=booking_payload(room_id, start_offset_days=30, email="guest@example.com", is_private_event=True),
        headers=booker_headers,
    )
    assert created.json()["status"] == "pending"
    pending_recipients = [r for _, r, _ in _FakeSMTP.sent]
    assert pending_recipients == [["guest@example.com"]]  # "request received"

    _FakeSMTP.sent = []
    await client.post(f"/api/admin/bookings/{created.json()['id']}/approve", json={}, headers=admin_headers)
    assert [r for _, r, _ in _FakeSMTP.sent] == [["guest@example.com"]]
    assert _decoded_subject(_FakeSMTP.sent[0][2]).endswith("| Joshua Generation Pinehurst")
