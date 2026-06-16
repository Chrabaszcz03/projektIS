"""REST API for WplywWydarzenNaCenyKryptowalut.

Run with:
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

Swagger UI: http://localhost:8000/docs
"""

import io
import json
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, hash_password, verify_password
from export_import import import_prices_xml, export_prices_xml
from models import (
    AnalysisResult,
    Cryptocurrency,
    Event,
    EventCategory,
    PriceHistory,
    User,
    get_engine,
    init_db,
)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()   # creates tables if they don't exist; no-op if they do
    yield


app = FastAPI(
    title="WplywWydarzenNaCenyKryptowalut API",
    version="1.0.0",
    lifespan=lifespan,
)


def get_db():
    db = Session(get_engine())
    try:
        yield db
    finally:
        db.close()


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Database error: {type(exc).__name__}"},
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class PriceRecord(BaseModel):
    id: int
    date: date
    price: float
    symbol: str

    model_config = {"from_attributes": True}


class PricesResponse(BaseModel):
    total: int
    items: list[PriceRecord]


class EventRecord(BaseModel):
    id: int
    title: str
    description: Optional[str]
    date: date
    category: str

    model_config = {"from_attributes": True}


class EventsResponse(BaseModel):
    total: int
    limit: int
    items: list[EventRecord]


class AnalysisRecord(BaseModel):
    id: int
    coin: str
    category: str
    n_event_days: int
    n_control_days: int
    mean_return_event: float
    mean_return_control: float
    std_event: float
    std_control: float
    t_stat: float
    p_value: float
    significant: bool

    model_config = {"from_attributes": True}


class ImpactResponse(BaseModel):
    event_id: int
    event_title: str
    category: str
    results: list[AnalysisRecord]


class ImportResponse(BaseModel):
    tickers_imported: list[str]
    rows_upserted: int


class EventPriceChangeRecord(BaseModel):
    date: date
    title: str
    category: str
    price: Optional[float]
    price_prev: Optional[float]
    pct_change: Optional[float]


class EventPriceChangesResponse(BaseModel):
    total: int
    items: list[EventPriceChangeRecord]


class UserCreate(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


# ---------------------------------------------------------------------------
# POST /api/auth/register  &  POST /api/auth/login
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Nazwa użytkownika jest już zajęta")
    db.add(User(username=body.username, hashed_password=hash_password(body.password)))
    db.commit()
    return {"message": "Użytkownik zarejestrowany"}


@app.post("/api/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Nieprawidłowa nazwa użytkownika lub hasło",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.username), token_type="bearer")


# ---------------------------------------------------------------------------
# GET /api/prices
# ---------------------------------------------------------------------------

@app.get("/api/prices", response_model=PricesResponse)
def get_prices(
    crypto: str = Query(..., description="Ticker symbol, e.g. BTC or ETH"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    coin_row = db.query(Cryptocurrency).filter(
        Cryptocurrency.symbol == crypto.upper()
    ).first()
    if coin_row is None:
        raise HTTPException(status_code=404, detail=f"Unknown crypto symbol: {crypto}")

    q = db.query(PriceHistory).filter(PriceHistory.crypto_id == coin_row.id)
    if from_date:
        q = q.filter(PriceHistory.date >= from_date)
    if to_date:
        q = q.filter(PriceHistory.date <= to_date)
    rows = q.order_by(PriceHistory.date).all()

    items = [
        PriceRecord(id=r.id, date=r.date, price=r.price, symbol=coin_row.symbol)
        for r in rows
    ]
    return PricesResponse(total=len(items), items=items)


# ---------------------------------------------------------------------------
# GET /api/events
# ---------------------------------------------------------------------------

@app.get("/api/events", response_model=EventsResponse)
def get_events(
    category: Optional[str] = Query(None, description="Category name (Polish), e.g. Gospodarka"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=10000, description="Max records returned"),
    db: Session = Depends(get_db),
):
    q = db.query(Event).join(EventCategory, Event.category_id == EventCategory.id)

    if category:
        cat_row = db.query(EventCategory).filter(EventCategory.name == category).first()
        if cat_row is None:
            raise HTTPException(status_code=404, detail=f"Unknown category: {category}")
        q = q.filter(Event.category_id == cat_row.id)

    if from_date:
        q = q.filter(Event.date >= from_date)
    if to_date:
        q = q.filter(Event.date <= to_date)

    rows = q.order_by(Event.date.desc()).limit(limit).all()

    items = [
        EventRecord(
            id=r.id,
            title=r.title or "",
            description=r.description,
            date=r.date,
            category=r.category.name,
        )
        for r in rows
    ]
    return EventsResponse(total=len(items), limit=limit, items=items)


# ---------------------------------------------------------------------------
# POST /api/import/xml
# ---------------------------------------------------------------------------

@app.post("/api/import/xml", response_model=ImportResponse)
def import_xml(
    file: UploadFile = File(..., description="XML file produced by export_prices_xml()"),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
        tmp_path = tmp.name
        tmp.write(file.file.read())

    try:
        prices_by_ticker = import_prices_xml(tmp_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"XML parse error: {exc}")
    finally:
        os.unlink(tmp_path)

    tickers_imported: list[str] = []
    total_upserted = 0

    for ticker, df in prices_by_ticker.items():
        coin_row = db.query(Cryptocurrency).filter(
            Cryptocurrency.symbol == ticker
        ).first()
        if coin_row is None:
            coin_row = Cryptocurrency(symbol=ticker, name=ticker.lower())
            db.add(coin_row)
            db.flush()

        existing = {
            row.date: row
            for row in db.query(PriceHistory).filter(
                PriceHistory.crypto_id == coin_row.id
            ).all()
        }

        for record in df.itertuples(index=False):
            day = record.date.date() if hasattr(record.date, "date") else record.date
            price = float(record.price)

            if day in existing:
                if existing[day].price != price:
                    existing[day].price = price
            else:
                db.add(PriceHistory(crypto_id=coin_row.id, date=day, price=price))
            total_upserted += 1

        tickers_imported.append(ticker)

    db.commit()
    return ImportResponse(tickers_imported=tickers_imported, rows_upserted=total_upserted)


# ---------------------------------------------------------------------------
# GET /api/analysis/impact
# ---------------------------------------------------------------------------

@app.get("/api/analysis/impact", response_model=ImpactResponse)
def get_impact(
    event_id: int = Query(..., description="Primary key of an Event row"),
    db: Session = Depends(get_db),
):
    event_row = db.query(Event).filter(Event.id == event_id).first()
    if event_row is None:
        raise HTTPException(status_code=404, detail=f"Event not found: id={event_id}")

    category_name = event_row.category.name

    analysis_rows = db.query(AnalysisResult).filter(
        AnalysisResult.category == category_name
    ).all()
    if not analysis_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis results for category: {category_name}. Run main.py first.",
        )

    results = [
        AnalysisRecord(
            id=r.id,
            coin=r.coin,
            category=r.category,
            n_event_days=r.n_event_days,
            n_control_days=r.n_control_days,
            mean_return_event=r.mean_return_event,
            mean_return_control=r.mean_return_control,
            std_event=r.std_event,
            std_control=r.std_control,
            t_stat=r.t_stat,
            p_value=r.p_value,
            significant=bool(r.significant),
        )
        for r in analysis_rows
    ]

    return ImpactResponse(
        event_id=event_id,
        event_title=event_row.title or "",
        category=category_name,
        results=results,
    )


# ---------------------------------------------------------------------------
# GET /api/analysis/results
# ---------------------------------------------------------------------------

class AnalysisResultsResponse(BaseModel):
    total: int
    items: list[AnalysisRecord]


@app.get("/api/analysis/results", response_model=AnalysisResultsResponse)
def get_analysis_results(
    coin: Optional[str] = Query(None, description="BTC lub ETH"),
    db: Session = Depends(get_db),
):
    q = db.query(AnalysisResult)
    if coin:
        q = q.filter(AnalysisResult.coin == coin.upper())
    rows = q.order_by(AnalysisResult.category).all()
    items = [
        AnalysisRecord(
            id=r.id,
            coin=r.coin,
            category=r.category,
            n_event_days=r.n_event_days,
            n_control_days=r.n_control_days,
            mean_return_event=r.mean_return_event,
            mean_return_control=r.mean_return_control,
            std_event=r.std_event,
            std_control=r.std_control,
            t_stat=r.t_stat,
            p_value=r.p_value,
            significant=bool(r.significant),
        )
        for r in rows
    ]
    return AnalysisResultsResponse(total=len(items), items=items)


# ---------------------------------------------------------------------------
# GET /api/categories
# ---------------------------------------------------------------------------

@app.get("/api/categories", response_model=list[str])
def get_categories(db: Session = Depends(get_db)):
    rows = db.query(EventCategory).order_by(EventCategory.name).all()
    return [r.name for r in rows]


# ---------------------------------------------------------------------------
# GET /api/events/price-changes
# ---------------------------------------------------------------------------

@app.get("/api/events/price-changes", response_model=EventPriceChangesResponse)
def get_events_price_changes(
    crypto: str = Query(..., description="Ticker symbol, e.g. BTC or ETH"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    category: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    coin_row = db.query(Cryptocurrency).filter(
        Cryptocurrency.symbol == crypto.upper()
    ).first()
    if coin_row is None:
        raise HTTPException(status_code=404, detail=f"Unknown crypto symbol: {crypto}")

    price_q = db.query(PriceHistory).filter(PriceHistory.crypto_id == coin_row.id)
    price_lookup: dict[date, float] = {r.date: r.price for r in price_q.all()}

    eq = db.query(Event).join(EventCategory, Event.category_id == EventCategory.id)
    if category:
        cat_row = db.query(EventCategory).filter(EventCategory.name == category).first()
        if cat_row is None:
            raise HTTPException(status_code=404, detail=f"Unknown category: {category}")
        eq = eq.filter(Event.category_id == cat_row.id)
    if from_date:
        eq = eq.filter(Event.date >= from_date)
    if to_date:
        eq = eq.filter(Event.date <= to_date)

    events = eq.order_by(Event.date.desc()).limit(limit).all()

    items: list[EventPriceChangeRecord] = []
    for ev in events:
        d = ev.date
        price = price_lookup.get(d)
        prev_day = d - timedelta(days=1)
        price_prev = price_lookup.get(prev_day)
        pct = None
        if price is not None and price_prev is not None and price_prev != 0:
            pct = round((price - price_prev) / price_prev * 100, 4)
        items.append(EventPriceChangeRecord(
            date=d,
            title=ev.title or "",
            category=ev.category.name,
            price=price,
            price_prev=price_prev,
            pct_change=pct,
        ))

    return EventPriceChangesResponse(total=len(items), items=items)


# ---------------------------------------------------------------------------
# GET /api/export/events  (JSON download, auth required)
# ---------------------------------------------------------------------------

@app.get("/api/export/events")
def export_events(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    rows = db.query(Event).join(EventCategory, Event.category_id == EventCategory.id).all()
    records = [
        {"date": str(r.date), "title": r.title or "", "category": r.category.name}
        for r in rows
    ]
    payload = {"meta": {"schema_version": 1, "total": len(records)}, "records": records}
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="events_export.json"'},
    )


# ---------------------------------------------------------------------------
# GET /api/export/prices  (XML download, auth required)
# ---------------------------------------------------------------------------

@app.get("/api/export/prices")
def export_prices(
    crypto: Optional[str] = Query(None, description="Ticker, e.g. BTC. Omit for all."),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    coin_q = db.query(Cryptocurrency)
    if crypto:
        coin_q = coin_q.filter(Cryptocurrency.symbol == crypto.upper())
    coins = coin_q.all()
    if not coins:
        raise HTTPException(status_code=404, detail="No matching crypto found")

    import xml.etree.ElementTree as ET
    from datetime import datetime as dt

    root = ET.Element("prices")
    root.set("exported_at", dt.now().isoformat(timespec="seconds"))
    root.set("schema_version", "1")

    for coin in coins:
        coin_el = ET.SubElement(root, "coin", symbol=coin.symbol)
        rows = db.query(PriceHistory).filter(
            PriceHistory.crypto_id == coin.id
        ).order_by(PriceHistory.date).all()
        for r in rows:
            ET.SubElement(coin_el, "day", date=str(r.date), price=str(r.price))

    ET.indent(ET.ElementTree(root), space="  ")
    buf = io.BytesIO()
    ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
    return Response(
        content=buf.getvalue(),
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="prices_export.xml"'},
    )


# ---------------------------------------------------------------------------
# POST /api/import/json  (auth required)
# ---------------------------------------------------------------------------

@app.post("/api/import/json")
def import_json(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    try:
        payload = json.loads(file.file.read())
        records = payload["records"]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"JSON parse error: {exc}")

    imported = 0
    for rec in records:
        try:
            d = date.fromisoformat(rec["date"])
        except Exception:
            continue
        cat_name = rec.get("category", "Inne")
        cat_row = db.query(EventCategory).filter(EventCategory.name == cat_name).first()
        if cat_row is None:
            cat_row = EventCategory(name=cat_name)
            db.add(cat_row)
            db.flush()
        db.add(Event(
            title=rec.get("title", ""),
            description=rec.get("description"),
            date=d,
            category_id=cat_row.id,
        ))
        imported += 1

    db.commit()
    return {"imported": imported}


# ---------------------------------------------------------------------------
# Static frontend & root redirect
# ---------------------------------------------------------------------------

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")


@app.get("/")
def root():
    return RedirectResponse("/app/index.html")
