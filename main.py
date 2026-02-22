import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, func, Boolean
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

from pydantic import BaseModel, field_validator
from jose import jwt, JWTError
from passlib.context import CryptContext

# ==========================================
# 1. CONFIGURATION (ZERO .ENV)
# ==========================================
DATABASE_URL = "postgresql://postgres.nkpwevsanpauwkqcoobg:AgenceAuto2026Pro@aws-0-eu-central-1.pooler.supabase.com:6543/postgres?sslmode=require"
JWT_SECRET = "AgenceAutoSuperSecretKey2026"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "agence2026"
TOKEN_EXPIRY_HOURS = 24

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autopro")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def create_token(username: str) -> str:
    payload = {"sub": username, "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS), "iat": datetime.utcnow()}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        if payload.get("sub") is None: raise HTTPException(status_code=401, detail="Token invalide")
        return payload.get("sub")
    except JWTError: raise HTTPException(status_code=401, detail="Token expiré")

# ==========================================
# 2. DATABASE MODELS (FINANCIAL UPDATE)
# ==========================================
class VoitureDB(Base):
    __tablename__ = "voitures"
    id = Column(Integer, primary_key=True, index=True)
    marque = Column(String, nullable=False)
    matricule = Column(String, unique=True, nullable=False)
    statut = Column(String, default="Disponible")

class LocationDB(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    voiture_id = Column(Integer, ForeignKey("voitures.id"), nullable=False)
    date_sortie = Column(Date, nullable=False)
    jours = Column(Integer, nullable=False)
    date_retour = Column(Date, nullable=False)
    prix_total = Column(Float, nullable=False)
    montant_paye = Column(Float, default=0.0)
    caution = Column(String, default="Aucune")
    statut = Column(String, default="En cours")
    voiture = relationship("VoitureDB")

class DepenseDB(Base):
    __tablename__ = "depenses"
    id = Column(Integer, primary_key=True, index=True)
    voiture_id = Column(Integer, ForeignKey("voitures.id"), nullable=False)
    categorie = Column(String, nullable=False) # Lavage, Vidange, Mecanicien, Piece...
    montant = Column(Float, nullable=False)
    date_depense = Column(Date, nullable=False)
    voiture = relationship("VoitureDB")

# Jdida: Table dyal Assurance (Bhal kridi, katkhless 3la dfou3at)
class AssuranceDB(Base):
    __tablename__ = "assurances"
    id = Column(Integer, primary_key=True, index=True)
    voiture_id = Column(Integer, ForeignKey("voitures.id"), nullable=False)
    compagnie = Column(String, nullable=False)
    montant_total = Column(Float, nullable=False)
    montant_paye = Column(Float, default=0.0)
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date, nullable=False)
    voiture = relationship("VoitureDB")

class CreditDB(Base):
    __tablename__ = "credits"
    id = Column(Integer, primary_key=True, index=True)
    voiture_id = Column(Integer, ForeignKey("voitures.id"), unique=True, nullable=False)
    montant_total = Column(Float, nullable=False) # Chhal msselfin lbanka
    mensualite = Column(Float, nullable=False)    # Traita d ch'har
    montant_paye = Column(Float, default=0.0)     # Chhal dfe3na
    voiture = relationship("VoitureDB")

Base.metadata.create_all(bind=engine)

# ==========================================
# 3. PYDANTIC SCHEMAS
# ==========================================
class LoginData(BaseModel): username: str; password: str
class VoitureCreate(BaseModel): marque: str; matricule: str
class LocationCreate(BaseModel): voiture_id: int; date_sortie: date; jours: int; date_retour: date; prix_total: float; montant_paye: float = 0.0; caution: str = "Aucune"
class PaiementUpdate(BaseModel): montant_ajoute: float
class DepenseCreate(BaseModel): voiture_id: int; categorie: str; montant: float; date_depense: date
class AssuranceCreate(BaseModel): voiture_id: int; compagnie: str; montant_total: float; montant_paye: float = 0.0; date_debut: date; date_fin: date
class CreditCreate(BaseModel): voiture_id: int; montant_total: float; mensualite: float

# ==========================================
# 4. APP SETUP
# ==========================================
app = FastAPI(title="AutoPro ERP Cloud V4")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ==========================================
# 5. APIs DE BASE (Voitures & Locations)
# ==========================================
@app.post("/api/login/")
def login(data: LoginData):
    if data.username == ADMIN_USERNAME and data.password == ADMIN_PASSWORD:
        return {"success": True, "token": create_token(data.username)}
    raise HTTPException(status_code=401, detail="Identifiants incorrects")

@app.get("/api/voitures/")
def get_voitures(db: Session = Depends(get_db), _user: str = Depends(verify_token)): return db.query(VoitureDB).order_by(VoitureDB.marque).all()

@app.post("/api/voitures/")
def add_voiture(v: VoitureCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    try: db_v = VoitureDB(**v.model_dump()); db.add(db_v); db.commit(); return {"message": "ok"}
    except IntegrityError: db.rollback(); raise HTTPException(status_code=409, detail="Matricule existe déjà")

@app.get("/api/locations/")
def get_locations(db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    locs = db.query(LocationDB).order_by(LocationDB.id.desc()).all()
    return {"data": [{"id": l.id, "voiture_id": l.voiture_id, "marque": l.voiture.marque, "matricule": l.voiture.matricule, "date_sortie": l.date_sortie.isoformat(), "date_retour": l.date_retour.isoformat(), "jours": l.jours, "prix_total": l.prix_total, "montant_paye": l.montant_paye, "reste": round(l.prix_total - l.montant_paye, 2), "caution": l.caution, "statut": l.statut} for l in locs]}

@app.post("/api/locations/")
def add_location(loc: LocationCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    v = db.query(VoitureDB).filter(VoitureDB.id == loc.voiture_id).first()
    db_loc = LocationDB(**loc.model_dump()); db.add(db_loc); v.statut = "En Location"; db.commit(); return {"message": "ok"}

@app.put("/api/locations/{loc_id}/payer")
def payer_reste_loc(loc_id: int, p: PaiementUpdate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    loc = db.query(LocationDB).filter(LocationDB.id == loc_id).first()
    loc.montant_paye = round(loc.montant_paye + p.montant_ajoute, 2); db.commit(); return {"message": "ok"}

@app.put("/api/locations/{loc_id}/retourner")
def retourner_voiture(loc_id: int, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    loc = db.query(LocationDB).filter(LocationDB.id == loc_id).first()
    loc.statut = "Terminée"; db.query(VoitureDB).filter(VoitureDB.id == loc.voiture_id).first().statut = "Disponible"; db.commit(); return {"message": "ok"}

# ==========================================
# 6. APIs FINANCIERS (Dépenses, Assurance, Crédit)
# ==========================================
@app.post("/api/depenses/")
def add_depense(dep: DepenseCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    db.add(DepenseDB(**dep.model_dump())); db.commit(); return {"message": "ok"}

@app.get("/api/depenses/")
def get_depenses(db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    return [{"id": d.id, "marque": d.voiture.marque, "categorie": d.categorie, "montant": d.montant, "date": d.date_depense.isoformat()} for d in db.query(DepenseDB).order_by(DepenseDB.date_depense.desc()).all()]

@app.post("/api/assurances/")
def add_assurance(a: AssuranceCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    db.add(AssuranceDB(**a.model_dump())); db.commit(); return {"message": "ok"}

@app.get("/api/assurances/")
def get_assurances(db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    return [{"id": a.id, "marque": a.voiture.marque, "matricule": a.voiture.matricule, "compagnie": a.compagnie, "montant_total": a.montant_total, "montant_paye": a.montant_paye, "reste": a.montant_total - a.montant_paye, "date_fin": a.date_fin.isoformat()} for a in db.query(AssuranceDB).all()]

@app.put("/api/assurances/{a_id}/payer")
def payer_assurance(a_id: int, p: PaiementUpdate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    a = db.query(AssuranceDB).filter(AssuranceDB.id == a_id).first()
    a.montant_paye = round(a.montant_paye + p.montant_ajoute, 2); db.commit(); return {"message": "ok"}

@app.post("/api/credits/")
def add_credit(c: CreditCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    try: db.add(CreditDB(**c.model_dump())); db.commit(); return {"message": "ok"}
    except IntegrityError: db.rollback(); raise HTTPException(status_code=409, detail="Crédit existe déjà pour cette voiture")

@app.get("/api/credits/")
def get_credits(db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    return [{"id": c.id, "marque": c.voiture.marque, "montant_total": c.montant_total, "mensualite": c.mensualite, "montant_paye": c.montant_paye, "reste": c.montant_total - c.montant_paye} for c in db.query(CreditDB).all()]

@app.put("/api/credits/{c_id}/payer")
def payer_traita(c_id: int, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    c = db.query(CreditDB).filter(CreditDB.id == c_id).first()
    c.montant_paye = round(c.montant_paye + c.mensualite, 2); db.commit(); return {"message": "ok"}

# ==========================================
# 7. DASHBOARD FINANCIER (ANALYSE PRO)
# ==========================================
@app.get("/api/dashboard/")
def get_dashboard(db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    # 1. Revenus (Lflouss li dkhlat mn lkriya)
    revenu_total = db.query(func.sum(LocationDB.montant_paye)).scalar() or 0.0
    kridi_3la_lketyan = db.query(func.sum(LocationDB.prix_total - LocationDB.montant_paye)).filter(LocationDB.statut == "En cours").scalar() or 0.0
    
    # 2. Charges (Masarif)
    depenses_auto = db.query(func.sum(DepenseDB.montant)).scalar() or 0.0
    assurances_payees = db.query(func.sum(AssuranceDB.montant_paye)).scalar() or 0.0
    credits_payes = db.query(func.sum(CreditDB.montant_paye)).scalar() or 0.0
    
    total_charges = depenses_auto + assurances_payees + credits_payes
    profit_net = revenu_total - total_charges

    # 3. Flotte
    total_voitures = db.query(func.count(VoitureDB.id)).scalar() or 0
    en_location = db.query(func.count(VoitureDB.id)).filter(VoitureDB.statut == "En Location").scalar() or 0

    return {
        "finances": {
            "revenu_total": round(revenu_total, 2),
            "kridi_m3a_kleyan": round(kridi_3la_lketyan, 2), # Lflouss li mazal kantsalouha l kleyan
            "charges_detail": {
                "lavage_mecanique_etc": round(depenses_auto, 2),
                "assurances_payees": round(assurances_payees, 2),
                "traites_payees": round(credits_payes, 2)
            },
            "total_charges": round(total_charges, 2),
            "profit_net": round(profit_net, 2) # Lrbe7 dyal bessa7 mn b3d masarif
        },
        "voitures": {
            "total": total_voitures,
            "en_location": en_location
        }
    }
