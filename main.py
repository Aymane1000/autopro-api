from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from pydantic import BaseModel
from datetime import date

# ==========================================
# 1. CONFIGURATION BASE DE DONNÉES (SUPABASE)
# ==========================================
# ⚠️ ATTENTION: Bdell [YOUR-PASSWORD] b l'mot de passe dyalek s7i7 bla m39oufat []
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:[Yuuol00--ia123@dwndw7383834@SSccvv]@db.nkpwevsanpauwkqcoobg.supabase.co:5432/postgres"

# 7iydna connect_args dyal SQLite 7it PostgreSQL pro w kheddam mzyan f l'Cloud
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 2. MODÈLES DE BASE DE DONNÉES (TABLES)
# ==========================================
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

# Hna Python kaymchi l Supabase w kaycreer les tables bohdou ila makanoch
Base.metadata.create_all(bind=engine)

# ==========================================
# 3. SCHÉMAS PYDANTIC (Validation des données)
# ==========================================
class VoitureCreate(BaseModel): 
    marque: str
    matricule: str

class LocationCreate(BaseModel): 
    voiture_id: int
    date_sortie: date
    jours: int
    date_retour: date
    prix_total: float
    montant_paye: float

class PaiementUpdate(BaseModel): 
    montant_ajoute: float

class DepenseCreate(BaseModel): 
    voiture_id: int
    categorie: str
    montant: float
    date_depense: date

class CreditCreate(BaseModel): 
    voiture_id: int
    montant_total: float
    mensualite: float

class LoginData(BaseModel): 
    username: str
    password: str

# ==========================================
# 4. INITIALISATION DE L'APPLICATION
# ==========================================
app = FastAPI(title="AutoPro ERP API - Cloud Version")

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

def get_db():
    db = SessionLocal()
    try: 
        yield db
    finally: 
        db.close()

# ==========================================
# 5. ROUTES / APIs
# ==========================================

# --- SÉCURITÉ (LOGIN) ---
@app.post("/api/login/")
def login(data: LoginData):
    if data.username == "admin" and data.password == "agence2026":
        return {"success": True, "message": "Mrehba bik a l'M3ellem!"}
    else:
        raise HTTPException(status_code=401, detail="L'username wla l'mot de passe ghalat!")

# --- VOITURES (FLOTTE) ---
@app.post("/api/voitures/")
def add_voiture(v: VoitureCreate, db: Session = Depends(get_db)):
    db.add(VoitureDB(**v.dict()))
    db.commit()
    return {"message": "Voiture ajoutée b naja7"}

@app.get("/api/voitures/")
def get_voitures(db: Session = Depends(get_db)): 
    return db.query(VoitureDB).all()

# --- LOCATIONS (KRIYA) ---
@app.post("/api/locations/")
def add_location(loc: LocationCreate, db: Session = Depends(get_db)):
    db_loc = LocationDB(**loc.dict())
    db.add(db_loc)
    
    # Nbadlou statut dyal tomobila
    voiture = db.query(VoitureDB).filter(VoitureDB.id == loc.voiture_id).first()
    if voiture: 
        voiture.statut = "En Location"
        
    db.commit()
    return {"message": "Location enregistrée"}

@app.get("/api/locations/")
def get_locations(db: Session = Depends(get_db)):
    # Njibou l'kriyat mretbin mn jdid lqdim (Order By Desc)
    locations = db.query(LocationDB).order_by(LocationDB.id.desc()).all()
    return [{
        "id": l.id, 
        "voiture_id": l.voiture_id, 
        "marque": l.voiture.marque, 
        "matricule": l.voiture.matricule, 
        "date_sortie": l.date_sortie, 
        "date_retour": l.date_retour, 
        "jours": l.jours, 
        "prix_total": l.prix_total, 
        "montant_paye": l.montant_paye, 
        "reste": l.prix_total - l.montant_paye, 
        "statut": l.statut
    } for l in locations]

@app.put("/api/locations/{loc_id}/payer")
def payer_reste(loc_id: int, paiement: PaiementUpdate, db: Session = Depends(get_db)):
    loc = db.query(LocationDB).filter(LocationDB.id == loc_id).first()
    if loc: 
        loc.montant_paye += paiement.montant_ajoute
        db.commit()
    return {"message": "Khlas dzad"}

@app.put("/api/locations/{loc_id}/retourner")
def retourner_voiture(loc_id: int, db: Session = Depends(get_db)):
    loc = db.query(LocationDB).filter(LocationDB.id == loc_id).first()
    if loc:
        loc.statut = "Terminée"
        voiture = db.query(VoitureDB).filter(VoitureDB.id == loc.voiture_id).first()
        if voiture: 
            voiture.statut = "Disponible" 
        db.commit()
    return {"message": "Tomobila rj3at l'garage"}

# --- DÉPENSES (MASARIF) ---
@app.post("/api/depenses/")
def add_depense(dep: DepenseCreate, db: Session = Depends(get_db)):
    db.add(DepenseDB(**dep.dict()))
    db.commit()
    return {"message": "Dépense ajoutée"}

@app.get("/api/depenses/")
def get_depenses(db: Session = Depends(get_db)):
    depenses = db.query(DepenseDB).all()
    return [{
        "id": d.id, 
        "voiture_id": d.voiture_id, 
        "marque": d.voiture.marque, 
        "montant": d.montant, 
        "date_depense": d.date_depense
    } for d in depenses]

# --- CRÉDITS BANKA ---
@app.post("/api/credits/")
def add_credit(cred: CreditCreate, db: Session = Depends(get_db)):
    db.add(CreditDB(**cred.dict()))
    db.commit()
    return {"message": "Crédit ajouté"}

@app.get("/api/credits/")
def get_credits(db: Session = Depends(get_db)):
    credits = db.query(CreditDB).all()
    return [{
        "id": c.id, 
        "marque": c.voiture.marque, 
        "matricule": c.voiture.matricule, 
        "montant_total": c.montant_total, 
        "mensualite": c.mensualite, 
        "montant_paye": c.montant_paye, 
        "reste": c.montant_total - c.montant_paye
    } for c in credits]

@app.put("/api/credits/{cred_id}/payer")
def payer_traita(cred_id: int, db: Session = Depends(get_db)):
    cred = db.query(CreditDB).filter(CreditDB.id == cred_id).first()
    if cred: 
        cred.montant_paye += cred.mensualite
        db.commit()
    return {"message": "Traita d chhar tkhlsat b naja7"}