from sqlalchemy.orm import Session
from models import ThermalAnomaly
from schemas import AnomalyCreate

def get_anomalies(db: Session):
    return db.query(ThermalAnomaly).all()

def create_anomaly(db: Session, anomaly: AnomalyCreate):
    db_anomaly = ThermalAnomaly(**anomaly.model_dump())
    db.add(db_anomaly)
    db.commit()
    db.refresh(db_anomaly)
    return db_anomaly