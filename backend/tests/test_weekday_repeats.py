from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from tests.conftest import make_room
from tests.test_calendar_sync import _make_admin

SAST = ZoneInfo("Africa/Johannesburg")  # UTC+2 all year


def local(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(SAST)


def body(room_ids, start_utc, until, frequency="weekly", weekdays=None, hours=2, **extra):
    start = datetime.fromisoformat(start_utc)
    rule = {"frequency": frequency, "until": f"{until}T00:00:00Z"}
    if weekdays is not None:
        rule["weekdays"] = weekdays
    return {
        "room_ids": room_ids,
        "requester_name": "Office",
        "congregation": "Youth Group",
        "email": "office@example.com",
        "phone": "+27820000000",
        "headcount": 20,
        "purpose": "Bible study",
        "start_time": start.isoformat(),
        "end_time": start.replace(hour=start.hour + hours).isoformat(),
        "recurrence": rule,
        **extra,
    }


async def create(client, admin, room, *args, **kwargs):
    return await client.post("/api/admin/bookings", json=body([room], *args, **kwargs), headers=admin)


def days(resp):
    return [local(b["start_time"]).strftime("%a %d %b %H:%M") for b in resp.json()["bookings"]]


async def setup(client, rooms_col):
    admin = await _make_admin(client)
    room = await make_room(rooms_col, name="Hall", capacity=300)
    return admin, room


async def test_monday_tuesday_and_friday_every_week(client, rooms_col):
    admin, room = await setup(client, rooms_col)
    # Monday 23 Nov 2026, 18:30 local (16:30 UTC), until Friday 4 Dec.
    resp = await create(client, admin, room, "2026-11-23T16:30:00", "2026-12-04", weekdays=[0, 1, 4])
    assert resp.status_code == 200, resp.text
    assert days(resp) == [
        "Mon 23 Nov 18:30", "Tue 24 Nov 18:30", "Fri 27 Nov 18:30",
        "Mon 30 Nov 18:30", "Tue 01 Dec 18:30", "Fri 04 Dec 18:30",
    ]
    assert resp.json()["created_count"] == 6 and resp.json()["series_id"]


async def test_any_combination_works_and_the_order_you_tick_does_not_matter(client, rooms_col):
    admin, room = await setup(client, rooms_col)
    resp = await create(client, admin, room, "2026-11-23T16:30:00", "2026-11-29", weekdays=[6, 2, 0, 2])  # Sun, Wed, Mon, Wed again
    assert days(resp) == ["Mon 23 Nov 18:30", "Wed 25 Nov 18:30", "Sun 29 Nov 18:30"]


async def test_a_start_day_that_is_not_ticked_is_not_booked(client, rooms_col):
    admin, room = await setup(client, rooms_col)
    # Wednesday 25 Nov start, but only Monday and Friday ticked: the first booking is Friday.
    resp = await create(client, admin, room, "2026-11-25T16:30:00", "2026-12-07", weekdays=[0, 4])
    assert days(resp) == ["Fri 27 Nov 18:30", "Mon 30 Nov 18:30", "Fri 04 Dec 18:30", "Mon 07 Dec 18:30"]


async def test_every_second_week_on_chosen_days(client, rooms_col):
    admin, room = await setup(client, rooms_col)
    resp = await create(client, admin, room, "2026-11-23T16:30:00", "2026-12-17", frequency="biweekly", weekdays=[0, 3])
    assert days(resp) == ["Mon 23 Nov 18:30", "Thu 26 Nov 18:30", "Mon 07 Dec 18:30", "Thu 10 Dec 18:30"]


async def test_the_until_day_itself_is_included(client, rooms_col):
    admin, room = await setup(client, rooms_col)
    resp = await create(client, admin, room, "2026-11-23T16:30:00", "2026-11-27", weekdays=[0, 4])
    assert days(resp) == ["Mon 23 Nov 18:30", "Fri 27 Nov 18:30"]


async def test_early_morning_bookings_stay_on_their_local_weekday(client, rooms_col):
    admin, room = await setup(client, rooms_col)
    # 00:30 local on Monday 23 Nov is 22:30 UTC on Sunday 22 Nov. "Monday" means the local Monday.
    resp = await create(client, admin, room, "2026-11-22T22:30:00", "2026-12-07", weekdays=[0], hours=1)
    assert days(resp) == ["Mon 23 Nov 00:30", "Mon 30 Nov 00:30", "Mon 07 Dec 00:30"]
    first_utc = datetime.fromisoformat(resp.json()["bookings"][0]["start_time"]).astimezone(timezone.utc)
    assert first_utc.strftime("%a %H:%M") == "Sun 22:30"


async def test_without_weekdays_a_weekly_repeat_works_exactly_as_before(client, rooms_col):
    admin, room = await setup(client, rooms_col)
    resp = await create(client, admin, room, "2026-11-23T16:30:00", "2026-12-07")
    assert days(resp) == ["Mon 23 Nov 18:30", "Mon 30 Nov 18:30", "Mon 07 Dec 18:30"]


async def test_the_chosen_days_are_checked(client, rooms_col):
    admin, room = await setup(client, rooms_col)
    for bad in ([], [7], [-1], ["mon"]):
        resp = await create(client, admin, room, "2026-11-23T16:30:00", "2026-12-04", weekdays=bad)
        assert resp.status_code == 422, bad
    monthly = await create(client, admin, room, "2026-11-23T16:30:00", "2027-02-23", frequency="monthly", weekdays=[0])
    assert monthly.status_code == 422


async def test_a_repeat_that_makes_only_one_booking_is_still_refused(client, rooms_col, bookings_col):
    admin, room = await setup(client, rooms_col)
    resp = await create(client, admin, room, "2026-11-23T16:30:00", "2026-11-26", weekdays=[0])
    assert resp.status_code == 400 and "only produces one booking" in resp.json()["detail"]
    assert await bookings_col.count_documents({}) == 0


async def test_a_run_that_would_be_too_long_is_refused(client, rooms_col, bookings_col):
    admin, room = await setup(client, rooms_col)
    resp = await create(client, admin, room, "2026-11-23T16:30:00", "2028-11-23", weekdays=[0, 1, 2, 3, 4, 5, 6])
    assert resp.status_code == 400 and "more than 104" in resp.json()["detail"]
    assert await bookings_col.count_documents({}) == 0


async def test_a_clash_on_any_chosen_day_creates_nothing(client, rooms_col, bookings_col):
    admin, room = await setup(client, rooms_col)
    # Someone already has the hall on Friday 27 Nov at 18:30.
    single = await client.post(
        "/api/admin/bookings", json={**body([room], "2026-11-27T16:30:00", "2026-11-27"), "recurrence": None}, headers=admin
    )
    assert single.status_code == 200
    assert await bookings_col.count_documents({}) == 1

    resp = await create(client, admin, room, "2026-11-23T16:30:00", "2026-12-04", weekdays=[0, 4])
    assert resp.status_code == 409 and "27 Nov" in resp.json()["detail"] and "nothing was created" in resp.json()["detail"]
    assert await bookings_col.count_documents({}) == 1  # not even the Mondays were made


async def test_several_rooms_at_once_each_get_every_chosen_day(client, rooms_col):
    admin = await _make_admin(client)
    hall = await make_room(rooms_col, name="Hall", capacity=300)
    foyer = await make_room(rooms_col, name="Foyer", capacity=80)
    resp = await client.post(
        "/api/admin/bookings", json=body([hall, foyer], "2026-11-23T16:30:00", "2026-11-27", weekdays=[0, 2, 4]), headers=admin
    )
    assert resp.status_code == 200, resp.text
    made = resp.json()["bookings"]
    assert len(made) == 6  # 3 days x 2 rooms
    assert len({b["series_id"] for b in made}) == 1 and len({b["group_id"] for b in made}) == 3
