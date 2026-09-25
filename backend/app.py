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


class CardItemIn(BaseModel):
    herb: str = Field(min_length=1, max_length=80)
    target_grams: float = Field(gt=0)


class CardIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    items: list[CardItemIn] = Field(min_length=1)


class CardWriteIn(BaseModel):
    item_id: int
    steps: list[StepIn] = Field(min_length=1)


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
        raise HTTPException(status_code=403, detail="仅炮制员可写入")
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
                created_at timestamptz NOT NULL,
                card_id integer,
                item_id integer
            )"""
        )
        # 兼容旧库：若 batches 已存在则补列
        cols = {r["column_name"] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='batches'"
        ).fetchall()}
        if "card_id" not in cols:
            conn.execute("ALTER TABLE batches ADD COLUMN card_id integer")
        if "item_id" not in cols:
            conn.execute("ALTER TABLE batches ADD COLUMN item_id integer")

        conn.execute(
            """CREATE TABLE IF NOT EXISTS rx_cards (
                id serial PRIMARY KEY,
                title text NOT NULL,
                created_by text NOT NULL,
                created_at timestamptz NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rx_items (
                id serial PRIMARY KEY,
                card_id integer NOT NULL REFERENCES rx_cards(id) ON DELETE CASCADE,
                herb text NOT NULL,
                target_grams numeric NOT NULL,
                ord integer NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rx_snapshots (
                id serial PRIMARY KEY,
                card_id integer NOT NULL REFERENCES rx_cards(id) ON DELETE CASCADE,
                seq integer NOT NULL,
                title text NOT NULL,
                issued_by text NOT NULL,
                issued_at timestamptz NOT NULL,
                UNIQUE (card_id, seq)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rx_snapshot_items (
                id serial PRIMARY KEY,
                snapshot_id integer NOT NULL REFERENCES rx_snapshots(id) ON DELETE CASCADE,
                herb text NOT NULL,
                target_grams numeric NOT NULL,
                write_count integer NOT NULL,
                pass_count integer NOT NULL,
                latest_verdict text,
                latest_reason text,
                latest_at timestamptz
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
            "SELECT id, herb, doc, verdict, reason, created_by FROM batches ORDER BY id DESC"
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
               RETURNING id, herb, doc, verdict, reason, created_by""",
            (body.herb.strip(), json.dumps(doc, ensure_ascii=False), verdict, reason,
             user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
    return row


# ---------------- 处方投料汇总卡 ----------------

def _card_summary(conn, card_id: int) -> dict:
    card = conn.execute(
        "SELECT id, title, created_by, created_at FROM rx_cards WHERE id=%s", (card_id,)
    ).fetchone()
    if card is None:
        raise HTTPException(status_code=404, detail="处方卡不存在")
    items = conn.execute(
        """SELECT i.id, i.herb, i.target_grams,
                  COUNT(b.id) AS write_count,
                  COUNT(b.id) FILTER (WHERE b.verdict='放行') AS pass_count,
                  (ARRAY_AGG(b.verdict ORDER BY b.id DESC))[1] AS latest_verdict,
                  (ARRAY_AGG(b.reason  ORDER BY b.id DESC))[1] AS latest_reason,
                  MAX(b.created_at) AS latest_at
             FROM rx_items i
             LEFT JOIN batches b ON b.item_id=i.id
            WHERE i.card_id=%s
            GROUP BY i.id
            ORDER BY i.ord""",
        (card_id,),
    ).fetchall()
    snaps = conn.execute(
        """SELECT id, seq, title, issued_by, issued_at,
                  (SELECT COUNT(*) FROM rx_snapshot_items si WHERE si.snapshot_id=rx_snapshots.id) AS item_count
             FROM rx_snapshots WHERE card_id=%s ORDER BY seq DESC""",
        (card_id,),
    ).fetchall()
    return {"card": card, "items": items, "snapshots": snaps}


@app.post("/api/rx/cards", status_code=201)
def create_card(body: CardIn, user: dict = Depends(require_writer)):
    now = datetime.now(timezone.utc)
    with connect() as conn:
        card = conn.execute(
            "INSERT INTO rx_cards (title, created_by, created_at) VALUES (%s,%s,%s) RETURNING id",
            (body.title.strip(), user["username"], now),
        ).fetchone()
        for ord_, it in enumerate(body.items, start=1):
            conn.execute(
                "INSERT INTO rx_items (card_id, herb, target_grams, ord) VALUES (%s,%s,%s,%s)",
                (card["id"], it.herb.strip(), it.target_grams, ord_),
            )
        conn.commit()
        return _card_summary(conn, card["id"])


@app.get("/api/rx/cards")
def list_cards(_user: dict = Depends(current_user)):
    with connect() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM rx_cards ORDER BY id DESC").fetchall()]
        return [_card_summary(conn, cid) for cid in ids]


@app.get("/api/rx/cards/{card_id}")
def get_card(card_id: int, _user: dict = Depends(current_user)):
    with connect() as conn:
        return _card_summary(conn, card_id)


@app.post("/api/rx/cards/{card_id}/writes", status_code=201)
def card_write(card_id: int, body: CardWriteIn, user: dict = Depends(require_writer)):
    doc = {"steps": [s.model_dump() for s in body.steps]}
    verdict, reason = judge(doc)
    with connect() as conn:
        item = conn.execute(
            "SELECT id, herb FROM rx_items WHERE id=%s AND card_id=%s",
            (body.item_id, card_id),
        ).fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="该味不在此处方卡上")
        conn.execute(
            """INSERT INTO batches (herb, doc, verdict, reason, created_by, created_at, card_id, item_id)
               VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s)""",
            (item["herb"], json.dumps(doc, ensure_ascii=False), verdict, reason,
             user["username"], datetime.now(timezone.utc), card_id, item["id"]),
        )
        conn.commit()
        return _card_summary(conn, card_id)


@app.post("/api/rx/cards/{card_id}/snapshots", status_code=201)
def issue_snapshot(card_id: int, user: dict = Depends(require_writer)):
    now = datetime.now(timezone.utc)
    with connect() as conn:
        try:
            seq = conn.execute(
                "SELECT COALESCE(MAX(seq),0)+1 AS seq FROM rx_snapshots WHERE card_id=%s",
                (card_id,),
            ).fetchone()["seq"]
            snap = conn.execute(
                """INSERT INTO rx_snapshots (card_id, seq, title, issued_by, issued_at)
                   SELECT %s, %s, title, %s, %s FROM rx_cards WHERE id=%s
                   RETURNING id, title""",
                (card_id, seq, user["username"], now, card_id),
            ).fetchone()
            if snap is None:
                raise HTTPException(status_code=404, detail="处方卡不存在")
            # 冻结签发当时各味的次数与最近结论
            conn.execute(
                """INSERT INTO rx_snapshot_items
                       (snapshot_id, herb, target_grams, write_count, pass_count,
                        latest_verdict, latest_reason, latest_at)
                   SELECT %s, i.herb, i.target_grams,
                          COUNT(b.id),
                          COUNT(b.id) FILTER (WHERE b.verdict='放行'),
                          (ARRAY_AGG(b.verdict ORDER BY b.id DESC))[1],
                          (ARRAY_AGG(b.reason  ORDER BY b.id DESC))[1],
                          MAX(b.created_at)
                     FROM rx_items i
                     LEFT JOIN batches b ON b.item_id=i.id
                    WHERE i.card_id=%s
                    GROUP BY i.id
                    ORDER BY i.ord""",
                (snap["id"], card_id),
            )
            conn.commit()
        except HTTPException:
            raise
        except Exception:
            conn.rollback()
            raise
        return get_snapshot(snap["id"], _user=user)


@app.get("/api/rx/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: int, _user: dict = Depends(current_user)):
    with connect() as conn:
        snap = conn.execute(
            "SELECT id, card_id, seq, title, issued_by, issued_at FROM rx_snapshots WHERE id=%s",
            (snapshot_id,),
        ).fetchone()
        if snap is None:
            raise HTTPException(status_code=404, detail="快照不存在")
        items = conn.execute(
            """SELECT herb, target_grams, write_count, pass_count,
                      latest_verdict, latest_reason, latest_at
                 FROM rx_snapshot_items WHERE snapshot_id=%s ORDER BY id""",
            (snapshot_id,),
        ).fetchall()
    return {"snapshot": snap, "items": items}
