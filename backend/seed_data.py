"""
Run once to populate placeholder rooms:
    python seed_data.py

Edit the ROOMS list below to match your actual campus before (or after)
running it — you can also edit rooms later from the admin portal.
"""
import asyncio
from app.database import rooms_collection

ROOMS = [
    {"name": "Main Hall", "type": "main_hall", "capacity": 300, "location": "Ground floor",
     "setup_notes": "Chairs in rows facing the stage, sound desk powered off, stage swept.",
     "photo_url": None, "active": True},
    {"name": "Training Hall A", "type": "training_hall", "capacity": 80, "location": "First floor",
     "setup_notes": "Tables in U-shape, whiteboard wiped, projector off.",
     "photo_url": None, "active": True},
    {"name": "Training Hall B", "type": "training_hall", "capacity": 60, "location": "First floor",
     "setup_notes": "Chairs stacked against back wall, floor swept.",
     "photo_url": None, "active": True},
    {"name": "Classroom 1", "type": "classroom", "capacity": 20, "location": "Second floor",
     "setup_notes": "Desks back in rows of 4, whiteboard wiped.",
     "photo_url": None, "active": True},
    {"name": "Classroom 2", "type": "classroom", "capacity": 20, "location": "Second floor",
     "setup_notes": "Desks back in rows of 4, whiteboard wiped.",
     "photo_url": None, "active": True},
    {"name": "Classroom 3", "type": "classroom", "capacity": 15, "location": "Second floor",
     "setup_notes": "Chairs in circle returned to rows, door locked.",
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
