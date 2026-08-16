from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from typing import Optional

class GarmentData(BaseModel):
    style_name: str
    main_color: str
    other_colors: Optional[str] = None  
    confidence: float
    timestamp: Optional[datetime] = None
    image_base64: Optional[str] = None