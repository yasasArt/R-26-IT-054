from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB URL (ඔයා MongoDB Atlas පාවිච්චි කරනවා නම්, මේක ඒ URL එකට මාරු කරන්න)
MONGO_DETAILS = "mongodb+srv://yasasjayaweera945_db_user:gjXDmB07oyYdebyy@cluster0.qhjffog.mongodb.net/?appName=Cluster0"

client = AsyncIOMotorClient(MONGO_DETAILS)

# Database එකේ නම 'garment_ai_db'
database = client.research

# Collection එකේ නම 'garments'
garment_collection = database.get_collection("ResearchBackend")