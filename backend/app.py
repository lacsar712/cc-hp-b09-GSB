import json
import os
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from rules import judge

SECRET = os.environ.get("JWT_SECRET", "herb-process-dev-secret")
DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54393/herb")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
USERS = {
    "processor": {"role": "writer", "password_hash": pwd.hash("herb123456")},
    "checker": {"role": "reader", "password_hash": pwd.hash("check123456")},
}


def connect():
    return psycopg.connect(DSN, row_factory=dict_row)


class LoginIn(BaseModel):
    username: str
    password: str


class StepIn(BaseModel):
    name: str
    temp_c: float
    minutes: float


class BatchIn(BaseModel):
    herb: str = Field(min_length=1, max_length=80)
    steps: list[StepIn]


class CardHerbIn(BaseModel):
    herb: str = Field(min_length=1, max_length=80)
    target_g: float = Field(gt=0)


class CardIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    herbs: list[CardHerbIn] = Field(min_length=1)


class CardEntryIn(BaseModel):
    herb: str = Field(min_length=1, max_length=80)
    steps: list[StepIn]


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="无效令牌") from exc
    if payload.get("sub") not in USERS:
        raise HTTPException(status_code=401, detail="无效令牌")
    return {"username": payload["sub"], "role": payload.get("role")}


def require_writer(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "writer":
        raise HTTPException(status_code=403, detail="仅炮制员可操作")
    return user


app = FastAPI(title="饮片炮制记录台")


@app.on_event("startup")
def startup():
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS batches (
                id serial PRIMARY KEY,
                herb text NOT NULL,
                doc jsonb NOT NULL,
                verdict text NOT NULL,
                reason text NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        # 处方投料汇总卡相关表
        conn.execute("ALTER TABLE batches ADD COLUMN IF NOT EXISTS card_id integer")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cards (
                id serial PRIMARY KEY,
                name text NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS card_herbs (
                id serial PRIMARY KEY,
                card_id integer NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                herb text NOT NULL,
                target_g double precision NOT NULL,
                ord integer NOT NULL,
                UNIQUE (card_id, herb)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS snapshots (
                id serial PRIMARY KEY,
                card_id integer NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                frozen_data jsonb NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        count = conn.execute("SELECT COUNT(*) AS n FROM batches").fetchone()["n"]
        if count == 0:
            now = datetime.now(timezone.utc)
            samples = [
                ("甘草", {"steps": [{"name": "清炒", "temp_c": 120, "minutes": 12}]}),
                ("黄芩", {"steps": [{"name": "清炒", "temp_c": 40, "minutes": 12}]}),
            ]
            for herb, doc in samples:
                verdict, reason = judge(doc)
                conn.execute(
                    """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
                       VALUES (%s, %s::jsonb, %s, %s, %s, %s)""",
                    (herb, json.dumps(doc, ensure_ascii=False), verdict, reason, "processor", now),
                )
        conn.commit()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "herb-process-record"}


@app.post("/api/auth/login")
def login(body: LoginIn):
    user = USERS.get(body.username.strip())
    if not user or not pwd.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode({"sub": body.username.strip(), "role": user["role"], "exp": exp}, SECRET, algorithm="HS256")
    return {"access_token": token, "username": body.username.strip(), "role": user["role"]}


@app.get("/api/batches")
def list_batches(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, herb, doc, verdict, reason, created_by, card_id FROM batches ORDER BY id DESC"
        ).fetchall()
    return rows


@app.post("/api/batches", status_code=201)
def create_batch(body: BatchIn, user: dict = Depends(require_writer)):
    doc = {"steps": [s.model_dump() for s in body.steps]}
    verdict, reason = judge(doc)
    with connect() as conn:
        row = conn.execute(
            """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at)
               VALUES (%s, %s::jsonb, %s, %s, %s, %s)
               RETURNING id, herb, doc, verdict, reason, created_by, card_id""",
            (body.herb.strip(), json.dumps(doc, ensure_ascii=False), verdict, reason, user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
    return row


# ---------- 处方投料汇总卡 ----------


def _freeze(conn, card: dict) -> dict:
    """汇总卡现场：各味目标克重、已成功写入次数、结论集合与最近结论。"""
    herbs = conn.execute(
        "SELECT herb, target_g FROM card_herbs WHERE card_id = %s ORDER BY ord",
        (card["id"],),
    ).fetchall()
    entries = conn.execute(
        """SELECT herb, verdict, reason, created_at
           FROM batches WHERE card_id = %s ORDER BY id""",
        (card["id"],),
    ).fetchall()
    by_herb: dict[str, list[dict]] = {}
    for e in entries:
        by_herb.setdefault(e["herb"], []).append(e)
    frozen_herbs = []
    for h in herbs:
        rows = by_herb.get(h["herb"], [])
        latest = rows[-1] if rows else None
        frozen_herbs.append(
            {
                "herb": h["herb"],
                "target_g": h["target_g"],
                "count": len(rows),
                "verdicts": sorted({r["verdict"] for r in rows}),
                "latest": (
                    {
                        "verdict": latest["verdict"],
                        "reason": latest["reason"],
                        "created_at": latest["created_at"].isoformat(),
                    }
                    if latest
                    else None
                ),
            }
        )
    return {
        "card_id": card["id"],
        "card_name": card["name"],
        "herbs": frozen_herbs,
    }


@app.get("/api/cards")
def list_cards(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.id, c.name, c.created_by, c.created_at,
                      (SELECT COUNT(*) FROM card_herbs h WHERE h.card_id = c.id) AS herb_count,
                      (SELECT COUNT(*) FROM snapshots s WHERE s.card_id = c.id) AS snapshot_count,
                      (SELECT MAX(created_at) FROM snapshots s WHERE s.card_id = c.id) AS last_snapshot_at
               FROM cards c ORDER BY c.id DESC"""
        ).fetchall()
    return rows


@app.post("/api/cards", status_code=201)
def create_card(body: CardIn, user: dict = Depends(require_writer)):
    names = [h.herb.strip() for h in body.herbs]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=422, detail="同一张卡内饮片不能重复")
    now = datetime.now(timezone.utc)
    with connect() as conn:
        card = conn.execute(
            "INSERT INTO cards (name, created_by, created_at) VALUES (%s, %s, %s) RETURNING id, name, created_by, created_at",
            (body.name.strip(), user["username"], now),
        ).fetchone()
        for i, h in enumerate(body.herbs):
            conn.execute(
                "INSERT INTO card_herbs (card_id, herb, target_g, ord) VALUES (%s, %s, %s, %s)",
                (card["id"], h.herb.strip(), h.target_g, i),
            )
        conn.commit()
    return {"id": card["id"]}


@app.get("/api/cards/{card_id}")
def get_card(card_id: int, _user: dict = Depends(current_user)):
    with connect() as conn:
        card = conn.execute("SELECT id, name, created_by, created_at FROM cards WHERE id = %s", (card_id,)).fetchone()
        if card is None:
            raise HTTPException(status_code=404, detail="处方卡不存在")
        freeze = _freeze(conn, card)
        snaps = conn.execute(
            "SELECT id, created_by, created_at FROM snapshots WHERE card_id = %s ORDER BY id DESC",
            (card_id,),
        ).fetchall()
    return {**card, "herbs": freeze["herbs"], "snapshots": snaps}


@app.post("/api/cards/{card_id}/entries", status_code=201)
def add_card_entry(card_id: int, body: CardEntryIn, user: dict = Depends(require_writer)):
    herb = body.herb.strip()
    with connect() as conn:
        card = conn.execute("SELECT id, name FROM cards WHERE id = %s", (card_id,)).fetchone()
        if card is None:
            raise HTTPException(status_code=404, detail="处方卡不存在")
        owned = conn.execute(
            "SELECT 1 FROM card_herbs WHERE card_id = %s AND herb = %s",
            (card_id, herb),
        ).fetchone()
        if owned is None:
            raise HTTPException(status_code=422, detail="该饮片不在这张处方卡上")
        doc = {"steps": [s.model_dump() for s in body.steps]}
        verdict, reason = judge(doc)
        row = conn.execute(
            """INSERT INTO batches (card_id, herb, doc, verdict, reason, created_by, created_at)
               VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)
               RETURNING id, herb, doc, verdict, reason, created_by, card_id""",
            (card_id, herb, json.dumps(doc, ensure_ascii=False), verdict, reason,
             user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
    return row


@app.post("/api/cards/{card_id}/snapshots", status_code=201)
def issue_snapshot(card_id: int, user: dict = Depends(require_writer)):
    """签发处方快照：冻结当时各味次数与结论集合；之后现场卡变化不影响快照。"""
    now = datetime.now(timezone.utc)
    with connect() as conn:
        card = conn.execute("SELECT id, name FROM cards WHERE id = %s", (card_id,)).fetchone()
        if card is None:
            raise HTTPException(status_code=404, detail="处方卡不存在")
        freeze = _freeze(conn, card)
        freeze["frozen_at"] = now.isoformat()
        row = conn.execute(
            """INSERT INTO snapshots (card_id, frozen_data, created_by, created_at)
               VALUES (%s, %s::jsonb, %s, %s) RETURNING id, card_id, created_by, created_at""",
            (card_id, json.dumps(freeze, ensure_ascii=False), user["username"], now),
        ).fetchone()
        conn.commit()
    return {**row, "freeze": freeze}


@app.get("/api/snapshots")
def list_snapshots(_user: dict = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute(
            """SELECT s.id, s.card_id, c.name AS card_name, s.created_by, s.created_at
               FROM snapshots s JOIN cards c ON c.id = s.card_id
               ORDER BY s.id DESC"""
        ).fetchall()
    return rows


@app.get("/api/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: int, _user: dict = Depends(current_user)):
    with connect() as conn:
        row = conn.execute(
            "SELECT id, card_id, frozen_data AS freeze, created_by, created_at FROM snapshots WHERE id = %s",
            (snapshot_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="快照不存在")
    return row
