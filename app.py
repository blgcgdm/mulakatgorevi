import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Header
import uvicorn
from pydantic import BaseModel, Field

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")

db_con = sqlite3.connect('mulakat.db', check_same_thread=False)


def init_db():
    cur = db_con.cursor()
    try:
        cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, is_admin INTEGER)")
        cur.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, body TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, text TEXT)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id)")
        db_con.commit()

        cur.execute("SELECT count(*) FROM users")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO users (name, email, is_admin) VALUES ('admin', 'admin@system.local', 1)")
            cur.execute("INSERT INTO users (name, email, is_admin) VALUES ('testuser', 'test@user.local', 0)")
            cur.execute("INSERT INTO posts (user_id, title, body) VALUES (1, 'System Boot', 'System is up and running.')")
            cur.execute("INSERT INTO comments (post_id, text) VALUES (1, 'First comment')")
            cur.execute("INSERT INTO comments (post_id, text) VALUES (1, 'Second comment')")
            db_con.commit()
    finally:
        cur.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    db_con.close()


app = FastAPI(lifespan=lifespan)


class UserIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200)


def require_admin(x_api_key: str = Header(None)):
    if not ADMIN_API_KEY or not x_api_key or not secrets.compare_digest(x_api_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Yetkisiz erisim")


@app.post("/users")
async def create_user(user: UserIn):
    if "@" not in user.email:
        raise HTTPException(status_code=422, detail="Gecersiz e-posta")

    cur = db_con.cursor()

    try:
        q = "INSERT INTO users (name, email, is_admin) VALUES (?, ?, ?)"
        cur.execute(q, (user.name, user.email, 0))
        db_con.commit()
        return {"status": "ok", "id": cur.lastrowid}
    except sqlite3.IntegrityError:
        db_con.rollback()
        raise HTTPException(status_code=409, detail="Bu e-posta zaten kayıtlı")
    finally:
        cur.close()


@app.get("/user_search")
async def get_user(name: str):
    cur = db_con.cursor()
    try:
        q = "SELECT id, name FROM users WHERE name=?"
        cur.execute(q, (name,))
        return cur.fetchall()
    finally:
        cur.close()


@app.get("/feed")
async def get_feed(limit: int = 20, offset: int = 0):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    cur = db_con.cursor()
    try:
        cur.execute(
            "SELECT id, user_id, title, body FROM posts ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset),
        )
        all_p = cur.fetchall()

        post_ids = [p[0] for p in all_p]
        if not post_ids:
            return []

        placeholders = ",".join("?" * len(post_ids))
        q = f"SELECT * FROM comments WHERE post_id IN ({placeholders})"
        cur.execute(q, post_ids)
        all_comments = cur.fetchall()

        comments_by_post = {}
        for c in all_comments:
            pid = c[1]
            if pid not in comments_by_post:
                comments_by_post[pid] = []
            comments_by_post[pid].append(c)

        temp_list = []
        for p in all_p:
            c = comments_by_post.get(p[0], [])
            temp_list.append({"post_info": p, "comments": c})

        return temp_list
    finally:
        cur.close()


@app.get("/all_data")
async def all_data(filter_text: str = "", limit: int = 50, offset: int = 0, _: None = Depends(require_admin)):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    cur = db_con.cursor()
    try:
        pattern = f"%{filter_text}%"
        cur.execute(
            "SELECT id, name, email, is_admin FROM users "
            "WHERE name LIKE ? OR email LIKE ? ORDER BY id LIMIT ? OFFSET ?",
            (pattern, pattern, limit, offset),
        )
        return cur.fetchall()
    finally:
        cur.close()


@app.get("/export")
async def export(_: None = Depends(require_admin)):
    cur = db_con.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        return {"count": count}
    finally:
        cur.close()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)