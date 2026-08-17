"""
Run once to populate placeholder rooms:
    python seed_data.py

Edit the ROOMS list below to match your actual campus before (or after)
running it — you can also edit rooms later from the admin portal.
"""
import asyncio
from app.database import areas_collection, congregations_collection, rooms_collection, booking_purposes_collection

ROOMS = [
    {"name": "Kids Classroom 1", "type": "classroom", "capacity": 30, "location": None,
     "setup_notes": "Chairs and tables back in rows, toys packed away, whiteboard wiped.",
     "photo_url": None, "active": True},
    {"name": "Kids Classroom 2", "type": "classroom", "capacity": 30, "location": None,
     "setup_notes": "Chairs and tables back in rows, toys packed away, whiteboard wiped.",
     "photo_url": None, "active": True},
    {"name": "Kids Classroom 3", "type": "classroom", "capacity": 30, "location": None,
     "setup_notes": "Chairs and tables back in rows, toys packed away, whiteboard wiped.",
     "photo_url": None, "active": True},
    {"name": "Kids Classroom 4", "type": "classroom", "capacity": 30, "location": None,
     "setup_notes": "Chairs and tables back in rows, toys packed away, whiteboard wiped.",
     "photo_url": None, "active": True},
    {"name": "Kids Classroom 5", "type": "classroom", "capacity": 30, "location": None,
     "setup_notes": "Chairs and tables back in rows, toys packed away, whiteboard wiped.",
     "photo_url": None, "active": True},
    {"name": "Main Hall", "type": "main_hall", "capacity": 600, "location": None,
     "setup_notes": "Chairs in rows facing the stage, sound desk powered off, stage swept.",
     "photo_url": None, "active": True},
    {"name": "Coffee Shop", "type": "coffee_shop", "capacity": 70, "location": None,
     "setup_notes": "Tables and chairs reset, counter wiped down, machines powered off.",
     "photo_url": None, "active": True},
    {"name": "Training Hall", "type": "training_hall", "capacity": 150, "location": None,
     "setup_notes": "Tables and chairs reset to standard layout, whiteboard wiped, projector off.",
     "photo_url": None, "active": True},
    {"name": "Lounge", "type": "lounge", "capacity": 30, "location": None,
     "setup_notes": "Furniture returned to normal layout, cups/dishes cleared.",
     "photo_url": None, "active": True},
    {"name": "Leap 1", "type": "leap", "capacity": 30, "location": None,
     "setup_notes": "Chairs and tables back in rows, toys packed away, whiteboard wiped.",
     "photo_url": None, "active": True},
    {"name": "Leap 2", "type": "leap", "capacity": 30, "location": None,
     "setup_notes": "Chairs and tables back in rows, toys packed away, whiteboard wiped.",
     "photo_url": None, "active": True},
]


BOOKING_PURPOSES = [
    "Sunday service",
    "Sunday school",
    "Bible study / cell group",
    "Youth ministry",
    "Kids ministry",
    "Worship practice / rehearsal",
    "Training / workshop",
    "Committee / admin meeting",
    "Outreach / community event",
    "Wedding",
    "Funeral / memorial",
    "Conference / seminar",
    "Other",
]


AREAS = [
    {"name": "Northern Hub", "always_requires_approval": False, "active": True},
    {"name": "Joshua Generation City", "always_requires_approval": True, "active": True},
]


async def seed():
    for room in ROOMS:
        await rooms_collection.update_one(
            {"name": room["name"]}, {"$set": room}, upsert=True
        )
    print(f"Seeded {len(ROOMS)} placeholder rooms.")

    for name in BOOKING_PURPOSES:
        await booking_purposes_collection.update_one(
            {"name": name}, {"$set": {"name": name, "active": True}}, upsert=True
        )
    print(f"Seeded {len(BOOKING_PURPOSES)} booking purposes.")

    for area in AREAS:
        await areas_collection.update_one(
            {"name": area["name"]}, {"$set": area}, upsert=True
        )
    print(f"Seeded {len(AREAS)} areas.")

    # One-time migration: any congregation created before areas existed has
    # no area_id yet. Default those to Northern Hub so the (now required)
    # area_id is never missing — reassign individual congregations to
    # Joshua Generation City afterward via the admin Manage Lists page.
    northern_hub = await areas_collection.find_one({"name": "Northern Hub"})
    if northern_hub:
        result = await congregations_collection.update_many(
            {"area_id": {"$in": [None, ""]}},
            {"$set": {"area_id": str(northern_hub["_id"])}},
        )
        if result.modified_count:
            print(f"Assigned {result.modified_count} existing congregation(s) to Northern Hub (review in Manage Lists).")


if __name__ == "__main__":
    asyncio.run(seed())
