import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from pydantic import BaseModel
from datetime import date

# ==========================================
# 1. CONFIGURATION DB (SUPABASE CLOUD - DEBUGGED)
# ==========================================
# ⚠️ Drna PORT 6543 (Transaction Mode) hit Render kiy7taj Connection Pooling
# ⚠️ Drna ?sslmode=require hit l'Cloud darori tkon l'connexion sécurisée
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:AgenceAuto2026Pro@db.nkpwevsanpauwkqcoobg.supabase.co:6543/postgres?sslmode=require"

# ANALYSE SENIOR:
# pool_pre_ping=True : Kat-testi l'khit m3a Supabase qbel ma y-crashi l'app
# pool_recycle=300   : Kat-sded l'connection l9dima kola 5 min (Bach Supabase may-sddoch 3lik)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODÈLES (TABLES) ---
class VoitureDB(Base):
    __tablename__ = "voitures"
    id = Column(Integer, primary_key=True, index=True)
    marque = Column(String)
    matricule = Column(String, unique=True)
    statut = Column(String, default="Disponible") 

class LocationDB(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    voiture_id = Column(Integer, ForeignKey("voitures.id"))
    date_sortie = Column(Date)
    jours = Column(Integer)
    date_retour = Column(Date)
    prix_total = Column(Float)
    montant_paye = Column(Float, default=0.0)
    caution = Column(String, default="Aucune")
    statut = Column(String, default="En cours")
    voiture = relationship("VoitureDB")

class DepenseDB(Base):
    __tablename__ = "depenses"
    id = Column(Integer, primary_key=True, index=True)
    voiture_id = Column(Integer, ForeignKey("voitures.id"))
    categorie = Column(String) 
    montant = Column(Float)
    date_depense = Column(Date)
    voiture = relationship("VoitureDB")

class CreditDB(Base):
    __tablename__ = "credits"
    id = Column(Integer, primary_key=True, index=True)
    voiture_id = Column(Integer, ForeignKey("voitures.id"), unique=True)
    montant_total = Column(Float) 
    mensualite = Column(Float) 
    montant_paye = Column(Float, default=0.0) 
    voiture = relationship("VoitureDB")

# Create tables
Base.metadata.create_all(bind=engine)

# --- SCHÉMAS ---
class VoitureCreate(BaseModel): marque: str; matricule: str
class LocationCreate(BaseModel): voiture_id: int; date_sortie: date; jours: int; date_retour: date; prix_total: float; montant_paye: float; caution: str
class PaiementUpdate(BaseModel): montant_ajoute: float
class DepenseCreate(BaseModel): voiture_id: int; categorie: str; montant: float; date_depense: date
class CreditCreate(BaseModel): voiture_id: int; montant_total: float; mensualite: float
class LoginData(BaseModel): username: str; password: str

# --- APP ---
app = FastAPI(title="AutoPro ERP Cloud")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- APIs ---
@app.post("/api/login/")
def login(data: LoginData):
    if data.username == "admin" and data.password == "agence2026":
        return {"success": True}
    raise HTTPException(status_code=401)

@app.get("/api/voitures/")
def get_voitures(db: Session = Depends(get_db)): return db.query(VoitureDB).all()

@app.post("/api/voitures/")
def add_voiture(v: VoitureCreate, db: Session = Depends(get_db)):
    db_v = VoitureDB(**v.dict()); db.add(db_v); db.commit(); return {"ok": True}

@app.get("/api/locations/")
def get_locations(db: Session = Depends(get_db)):
    locations = db.query(LocationDB).order_by(LocationDB.id.desc()).all()
    return [{"id": l.id, "marque": l.voiture.marque, "matricule": l.voiture.matricule, "date_sortie": l.date_sortie, "date_retour": l.date_retour, "prix_total": l.prix_total, "montant_paye": l.montant_paye, "reste": l.prix_total - l.montant_paye, "caution": l.caution, "statut": l.statut} for l in locations]

@app.post("/api/locations/")
def add_location(loc: LocationCreate, db: Session = Depends(get_db)):
    db_loc = LocationDB(**loc.dict()); db.add(db_loc)
    v = db.query(VoitureDB).filter(VoitureDB.id == loc.voiture_id).first()
    if v: v.statut = "En Location"
    db.commit(); return {"ok": True}

@app.put("/api/locations/{loc_id}/payer")
def payer_reste(loc_id: int, p: PaiementUpdate, db: Session = Depends(get_db)):
    loc = db.query(LocationDB).filter(LocationDB.id == loc_id).first()
    if loc: loc.montant_paye += p.montant_ajoute; db.commit(); return {"ok": True}

@app.put("/api/locations/{loc_id}/retourner")
def retourner_voiture(loc_id: int, db: Session = Depends(get_db)):
    loc = db.query(LocationDB).filter(LocationDB.id == loc_id).first()
    if loc:
        loc.statut = "Terminée"
        v = db.query(VoitureDB).filter(VoitureDB.id == loc.voiture_id).first()
        if v: v.statut = "Disponible"
        db.commit(); return {"ok": True}

@app.get("/api/depenses/")
def get_depenses(db: Session = Depends(get_db)):
    return [{"marque": d.voiture.marque, "montant": d.montant, "date": d.date_depense} for d in db.query(DepenseDB).all()]

@app.post("/api/depenses/")
def add_depense(dep: DepenseCreate, db: Session = Depends(get_db)):
    db.add(DepenseDB(**dep.dict())); db.commit(); return {"ok": True}

@app.get("/api/credits/")
def get_credits(db: Session = Depends(get_db)):
    credits = db.query(CreditDB).all()
    return [{"id": c.id, "marque": c.voiture.marque, "montant_total": c.montant_total, "mensualite": c.mensualite, "montant_paye": c.montant_paye, "reste": c.montant_total - c.montant_paye} for c in credits]

@app.post("/api/credits/")
def add_credit(c: CreditCreate, db: Session = Depends(get_db)):
    db.add(CreditDB(**c.dict())); db.commit(); return {"ok": True}

@app.put("/api/credits/{c_id}/payer")
def payer_traita(c_id: int, db: Session = Depends(get_db)):
    c = db.query(CreditDB).filter(CreditDB.id == c_id).first()
    if c: c.montant_paye += c.mensualite; db.commit(); return {"ok": True}
