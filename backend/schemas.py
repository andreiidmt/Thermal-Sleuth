from pydantic import BaseModel

# What the API receives
class AnomalyCreate(BaseModel):
    name: str
    lat: float
    lon: float
    temp_celsius: float

# What the API returns
class Anomaly(AnomalyCreate):
    id: int

    class Config:
        from_attributes = True