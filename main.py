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
# 1. CONFIGURATION (ZERO .ENV - KOLCHI HNA)
# ==========================================
# Zewwelna os.getenv w dkhlna l'ma3loumat mobachara

DATABASE_URL = "postgresql://postgres.nkpwevsanpauwkqcoobg:AgenceAuto2026Pro@aws-1-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require"
JWT_SECRET = "AgenceAutoSuperSecretKey2026"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "agence2026"
TOKEN_EXPIRY_HOURS = 24

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autopro")

# ==========================================
# 2. DATABASE ENGINE
# ==========================================
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 3. SECURITY — JWT
# ==========================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expiré ou invalide")

# ==========================================
# 4. DATABASE MODELS
# ==========================================
class ClientDB(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    telephone = Column(String, nullable=False)
    cin = Column(String, unique=True, nullable=False)
    permis = Column(String, default="")
    adresse = Column(String, default="")
    ville = Column(String, default="")
    notes = Column(String, default="")
    blackliste = Column(Boolean, default=False)
    created_at = Column(Date, default=date.today)
    locations = relationship("LocationDB", back_populates="client")

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
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    date_sortie = Column(Date, nullable=False)
    jours = Column(Integer, nullable=False)
    date_retour = Column(Date, nullable=False)
    prix_total = Column(Float, nullable=False)
    montant_paye = Column(Float, default=0.0)
    caution = Column(String, default="Aucune")
    statut = Column(String, default="En cours")
    voiture = relationship("VoitureDB")
    client = relationship("ClientDB", back_populates="locations")

class DepenseDB(Base):
    __tablename__ = "depenses"
    id = Column(Integer, primary_key=True, index=True)
    voiture_id = Column(Integer, ForeignKey("voitures.id"), nullable=False)
    categorie = Column(String, nullable=False)
    montant = Column(Float, nullable=False)
    date_depense = Column(Date, nullable=False)
    voiture = relationship("VoitureDB")

class CreditDB(Base):
    __tablename__ = "credits"
    id = Column(Integer, primary_key=True, index=True)
    voiture_id = Column(Integer, ForeignKey("voitures.id"), unique=True, nullable=False)
    montant_total = Column(Float, nullable=False)
    mensualite = Column(Float, nullable=False)
    montant_paye = Column(Float, default=0.0)
    voiture = relationship("VoitureDB")

Base.metadata.create_all(bind=engine)

# ==========================================
# 5. PYDANTIC SCHEMAS
# ==========================================
class LoginData(BaseModel):
    username: str
    password: str

class ClientCreate(BaseModel):
    nom: str
    telephone: str
    cin: str
    permis: str = ""
    adresse: str = ""
    ville: str = ""
    notes: str = ""

    @field_validator("nom")
    @classmethod
    def clean_nom(cls, v: str) -> str:
        if len(v.strip()) < 2: raise ValueError("Le nom doit contenir au moins 2 caractères")
        return v.strip()

    @field_validator("telephone")
    @classmethod
    def clean_tel(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if len(v) < 8: raise ValueError("Numéro de téléphone invalide")
        return v

    @field_validator("cin")
    @classmethod
    def clean_cin(cls, v: str) -> str:
        if len(v.strip()) < 3: raise ValueError("CIN invalide")
        return v.strip().upper()

class ClientUpdate(BaseModel):
    nom: Optional[str] = None
    telephone: Optional[str] = None
    cin: Optional[str] = None
    permis: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    notes: Optional[str] = None
    blackliste: Optional[bool] = None

class VoitureCreate(BaseModel):
    marque: str
    matricule: str

    @field_validator("matricule")
    @classmethod
    def normalize_matricule(cls, v: str) -> str: return v.strip().upper().replace("  ", " ")

    @field_validator("marque")
    @classmethod
    def clean_marque(cls, v: str) -> str: return v.strip()

class VoitureUpdate(BaseModel):
    marque: Optional[str] = None
    matricule: Optional[str] = None

class LocationCreate(BaseModel):
    voiture_id: int
    client_id: Optional[int] = None
    date_sortie: date
    jours: int
    date_retour: date
    prix_total: float
    montant_paye: float = 0.0
    caution: str = "Aucune"

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

# ==========================================
# 6. APP & MIDDLEWARE
# ==========================================
app = FastAPI(title="AutoPro ERP Cloud", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Zwelna ALLOWED_ORIGINS bach y9bel mn ay blassa fabor
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ==========================================
# 7. ROUTES — AUTH
# ==========================================
@app.post("/api/login/")
def login(data: LoginData):
    if data.username == ADMIN_USERNAME and data.password == ADMIN_PASSWORD:
        token = create_token(data.username)
        return {"success": True, "token": token}
    raise HTTPException(status_code=401, detail="Identifiants incorrects")

# ==========================================
# 8. ROUTES — CLIENTS (Protected)
# ==========================================
@app.get("/api/clients/")
def get_clients(search: Optional[str] = None, blackliste: Optional[bool] = None, page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    query = db.query(ClientDB)
    if search:
        s = f"%{search}%"
        query = query.filter((ClientDB.nom.ilike(s)) | (ClientDB.telephone.ilike(s)) | (ClientDB.cin.ilike(s)) | (ClientDB.ville.ilike(s)))
    if blackliste is not None: query = query.filter(ClientDB.blackliste == blackliste)
    total = query.count()
    clients = query.order_by(ClientDB.nom).offset((page - 1) * limit).limit(limit).all()
    result = []
    for c in clients:
        loc_count = db.query(func.count(LocationDB.id)).filter(LocationDB.client_id == c.id).scalar() or 0
        total_spent = db.query(func.sum(LocationDB.montant_paye)).filter(LocationDB.client_id == c.id).scalar() or 0.0
        active_locs = db.query(func.count(LocationDB.id)).filter(LocationDB.client_id == c.id, LocationDB.statut == "En cours").scalar() or 0
        result.append({
            "id": c.id, "nom": c.nom, "telephone": c.telephone, "cin": c.cin,
            "permis": c.permis, "adresse": c.adresse, "ville": c.ville,
            "notes": c.notes, "blackliste": c.blackliste,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "total_locations": loc_count, "total_depense": round(total_spent, 2), "locations_actives": active_locs,
        })
    return {"total": total, "page": page, "limit": limit, "data": result}

@app.post("/api/clients/", status_code=201)
def add_client(c: ClientCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    try:
        db_c = ClientDB(**c.model_dump()); db.add(db_c); db.commit(); db.refresh(db_c); return {"message": "ok", "id": db_c.id}
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail=f"CIN '{c.cin}' existe déjà")

@app.put("/api/clients/{client_id}")
def update_client(client_id: int, c: ClientUpdate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
    if not client: raise HTTPException(status_code=404, detail="Client non trouvé")
    update_data = c.model_dump(exclude_unset=True)
    for key, value in update_data.items(): setattr(client, key, value)
    try: db.commit(); return {"message": "ok"}
    except IntegrityError: db.rollback(); raise HTTPException(status_code=409, detail="CIN existe déjà")

@app.delete("/api/clients/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
    if not client: raise HTTPException(status_code=404, detail="Client non trouvé")
    db.delete(client); db.commit(); return {"message": "ok"}

@app.put("/api/clients/{client_id}/blacklist")
def toggle_blacklist(client_id: int, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
    if not client: raise HTTPException(status_code=404, detail="Client non trouvé")
    client.blackliste = not client.blackliste; db.commit()
    return {"message": "ok", "blackliste": client.blackliste}

# ==========================================
# 9. ROUTES — VOITURES (Protected)
# ==========================================
@app.get("/api/voitures/")
def get_voitures(db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    return db.query(VoitureDB).order_by(VoitureDB.marque).all()

@app.post("/api/voitures/", status_code=201)
def add_voiture(v: VoitureCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    try: db_v = VoitureDB(**v.model_dump()); db.add(db_v); db.commit(); db.refresh(db_v); return {"message": "ok", "id": db_v.id}
    except IntegrityError: db.rollback(); raise HTTPException(status_code=409, detail=f"Matricule '{v.matricule}' existe déjà")

@app.put("/api/voitures/{voiture_id}")
def update_voiture(voiture_id: int, v: VoitureUpdate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    voiture = db.query(VoitureDB).filter(VoitureDB.id == voiture_id).first()
    if not voiture: raise HTTPException(status_code=404, detail="Voiture non trouvée")
    if v.marque is not None: voiture.marque = v.marque.strip()
    if v.matricule is not None: voiture.matricule = v.matricule.strip().upper()
    try: db.commit(); return {"message": "ok"}
    except IntegrityError: db.rollback(); raise HTTPException(status_code=409, detail="Matricule existe déjà")

@app.delete("/api/voitures/{voiture_id}")
def delete_voiture(voiture_id: int, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    voiture = db.query(VoitureDB).filter(VoitureDB.id == voiture_id).first()
    if not voiture: raise HTTPException(status_code=404, detail="Voiture non trouvée")
    db.delete(voiture); db.commit(); return {"message": "ok"}

# ==========================================
# 10. ROUTES — LOCATIONS (Protected)
# ==========================================
@app.post("/api/locations/", status_code=201)
def add_location(loc: LocationCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    v = db.query(VoitureDB).filter(VoitureDB.id == loc.voiture_id).first()
    if not v: raise HTTPException(status_code=404, detail="Voiture non trouvée")
    db_loc = LocationDB(**loc.model_dump()); db.add(db_loc); v.statut = "En Location"; db.commit(); return {"message": "ok", "id": db_loc.id}

@app.get("/api/locations/")
def get_locations(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    locations = db.query(LocationDB).order_by(LocationDB.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"data": [{"id": l.id, "voiture_id": l.voiture_id, "marque": l.voiture.marque if l.voiture else "N/A", "matricule": l.voiture.matricule if l.voiture else "N/A", "date_sortie": l.date_sortie.isoformat(), "date_retour": l.date_retour.isoformat(), "jours": l.jours, "prix_total": l.prix_total, "montant_paye": l.montant_paye, "reste": round(l.prix_total - l.montant_paye, 2), "caution": l.caution, "statut": l.statut} for l in locations]}

@app.put("/api/locations/{loc_id}/payer")
def payer_reste(loc_id: int, p: PaiementUpdate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    loc = db.query(LocationDB).filter(LocationDB.id == loc_id).first()
    if loc: loc.montant_paye = round(loc.montant_paye + p.montant_ajoute, 2); db.commit()
    return {"message": "ok"}

@app.put("/api/locations/{loc_id}/retourner")
def retourner_voiture(loc_id: int, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    loc = db.query(LocationDB).filter(LocationDB.id == loc_id).first()
    if loc:
        loc.statut = "Terminée"; v = db.query(VoitureDB).filter(VoitureDB.id == loc.voiture_id).first()
        if v: v.statut = "Disponible"
        db.commit()
    return {"message": "ok"}

@app.delete("/api/locations/{loc_id}")
def delete_location(loc_id: int, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    loc = db.query(LocationDB).filter(LocationDB.id == loc_id).first()
    if loc: db.delete(loc); db.commit()
    return {"message": "ok"}

# ==========================================
# 11. ROUTES — DÉPENSES & CREDITS (Protected)
# ==========================================
@app.post("/api/depenses/", status_code=201)
def add_depense(dep: DepenseCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    db.add(DepenseDB(**dep.model_dump())); db.commit(); return {"message": "ok"}

@app.get("/api/depenses/")
def get_depenses(db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    deps = db.query(DepenseDB).order_by(DepenseDB.date_depense.desc()).all()
    return [{"id": d.id, "voiture_id": d.voiture_id, "marque": d.voiture.marque if d.voiture else "N/A", "categorie": d.categorie, "montant": d.montant, "date": d.date_depense.isoformat()} for d in deps]

@app.delete("/api/depenses/{dep_id}")
def delete_depense(dep_id: int, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    dep = db.query(DepenseDB).filter(DepenseDB.id == dep_id).first()
    if dep: db.delete(dep); db.commit()
    return {"message": "ok"}

@app.post("/api/credits/", status_code=201)
def add_credit(c: CreditCreate, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    db.add(CreditDB(**c.model_dump())); db.commit(); return {"message": "ok"}

@app.get("/api/credits/")
def get_credits(db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    credits = db.query(CreditDB).all()
    return [{"id": c.id, "voiture_id": c.voiture_id, "marque": c.voiture.marque if c.voiture else "N/A", "matricule": c.voiture.matricule if c.voiture else "N/A", "montant_total": c.montant_total, "mensualite": c.mensualite, "montant_paye": c.montant_paye, "reste": round(c.montant_total - c.montant_paye, 2)} for c in credits]

@app.put("/api/credits/{c_id}/payer")
def payer_traita(c_id: int, db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    c = db.query(CreditDB).filter(CreditDB.id == c_id).first()
    if c: c.montant_paye = round(c.montant_paye + c.mensualite, 2); db.commit()
    return {"message": "ok"}

# ==========================================
# 12. ROUTE — DASHBOARD (Protected)
# ==========================================
@app.get("/api/dashboard/")
def get_dashboard(db: Session = Depends(get_db), _user: str = Depends(verify_token)):
    total_voitures = db.query(func.count(VoitureDB.id)).scalar() or 0
    en_location = db.query(func.count(VoitureDB.id)).filter(VoitureDB.statut == "En Location").scalar() or 0
    revenu_total = db.query(func.sum(LocationDB.montant_paye)).scalar() or 0.0
    depenses_total = db.query(func.sum(DepenseDB.montant)).scalar() or 0.0
    return {
        "voitures": {"total": total_voitures, "en_location": en_location, "disponibles": total_voitures - en_location},
        "finances": {"revenu_total": round(revenu_total, 2), "depenses_total": round(depenses_total, 2), "profit_net": round(revenu_total - depenses_total, 2)},
    }

# ==========================================
# 13. HEALTH CHECK (Public)
# ==========================================
@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}

