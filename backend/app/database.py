from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db_name]

rooms_collection = db["rooms"]
bookings_collection = db["bookings"]
admins_collection = db["admins"]


async def ensure_indexes():
    await rooms_collection.create_index("name", unique=True)
    await bookings_collection.create_index([("room_id", 1), ("start_time", 1)])
    await bookings_collection.create_index("requester_email")
    await bookings_collection.create_index("status")
    await admins_collection.create_index("email", unique=True)
