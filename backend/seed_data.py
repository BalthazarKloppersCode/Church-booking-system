"""
Run once to populate placeholder rooms:
    python seed_data.py

Edit the ROOMS list below to match your actual campus before (or after)
running it — you can also edit rooms later from the admin portal.
"""
import asyncio
from app.database import rooms_collection

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
]


async def seed():
    for room in ROOMS:
        await rooms_collection.update_one(
            {"name": room["name"]}, {"$set": room}, upsert=True
        )
    print(f"Seeded {len(ROOMS)} placeholder rooms.")


if __name__ == "__main__":
    asyncio.run(seed())
