from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid  # අලුතින් එකතු කළ පැකේජය (ID සෑදීමට)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

garments_db = []

class GarmentData(BaseModel):
    style_name: str
    main_color: str
    other_colors: str
    confidence: float
    image_base64: str

@app.get("/")
async def root():
    return {"message": "ThreadScan Backend is Running Successfully!"}

@app.post("/api/garments/")
async def save_garment(garment: GarmentData):
    # Frontend එකට අලුත් දත්තයක් බව හඳුනාගැනීම සඳහා අද්විතීය ID එකක් එකතු කිරීම
    garment_dict = garment.model_dump()
    garment_dict["_id"] = str(uuid.uuid4()) 
    
    garments_db.insert(0, garment_dict)
    
    if len(garments_db) > 50:
        garments_db.pop()
        
    return {"status": "success", "message": "Garment saved successfully"}

@app.get("/api/garments/latest")
async def get_latest_garment():
    if len(garments_db) > 0:
        return garments_db[0]
    return None