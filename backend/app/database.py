from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db_name]

rooms_collection = db["rooms"]
bookings_collection = db["bookings"]
admins_collection = db["admins"]
congregations_collection = db["congregations"]
booking_purposes_collection = db["booking_purposes"]
areas_collection = db["areas"]
users_collection = db["users"]


async def ensure_indexes():
    await rooms_collection.create_index("name", unique=True)
    await bookings_collection.create_index([("room_id", 1), ("start_time", 1)])
    # "email" is the field actually queried (a booker looking up their own
    # bookings, or admin filtering) — the old index named "requester_email"
    # didn't match any real field and never got used.
    await bookings_collection.create_index("email")
    await bookings_collection.create_index("status")
    await bookings_collection.create_index("congregation")
    await bookings_collection.create_index("created_at")
    await admins_collection.create_index("email", unique=True)
    await congregations_collection.create_index("name", unique=True)
    await congregations_collection.create_index("area_id")
    await booking_purposes_collection.create_index("name", unique=True)
    await areas_collection.create_index("name", unique=True)
    await users_collection.create_index("email", unique=True)
