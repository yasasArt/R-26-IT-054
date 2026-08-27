import json
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import analytics
from database import get_connection
from models import CameraDevice, DowntimeEvent, GarmentData, Settings