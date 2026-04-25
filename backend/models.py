from sqlalchemy import Column, Integer, Float, String
from database import Base

class ThermalAnomaly(Base):
    __tablename__ = "anomalies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    temp_celsius = Column(Float)