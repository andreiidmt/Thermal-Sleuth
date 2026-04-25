from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base
import models, schemas, crud

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/anomalies/", response_model=schemas.Anomaly)
def add_anomaly(anomaly: schemas.AnomalyCreate, db: Session = Depends(get_db)):
    return crud.create_anomaly(db=db, anomaly=anomaly)

@app.get("/anomalies/")
def read_anomalies(db: Session = Depends(get_db)):
    return crud.get_anomalies(db)