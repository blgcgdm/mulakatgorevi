import os
import sqlite3
from fastapi import FastAPI, HTTPException, Depends, Header
import uvicorn
from pydantic import BaseModel

app = FastAPI()

class UserIn(BaseModel):
    name : str
    email : str
    
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")

def require_admin(x_api_key: str = Header(None)):
    if not ADMIN_API_KEY or x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Yetkisiz erisim")

db_con = sqlite3.connect('mulakat.db', check_same_thread=False)
cur = db_con.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, is_admin INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, body TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, text TEXT)")
db_con.commit()

cur.execute("SELECT count(*) FROM users")
if cur.fetchone()[0] == 0:
    cur.execute("INSERT INTO users (name, email, is_admin) VALUES ('admin', 'admin@system.local', 1)")
    cur.execute("INSERT INTO users (name, email, is_admin) VALUES ('testuser', 'test@user.local', 0)")
    cur.execute("INSERT INTO posts (user_id, title, body) VALUES (1, 'System Boot', 'System is up and running.')")
    cur.execute("INSERT INTO comments (post_id, text) VALUES (1, 'First comment')")
    cur.execute("INSERT INTO comments (post_id, text) VALUES (1, 'Second comment')")
    db_con.commit()


@app.post("/users")
async def create_user(user : UserIn):
    
    cur = db_con.cursor()

    try:
        
        q = "INSERT INTO users (name, email, is_admin) VALUES (?, ?, ?)"
        cur.execute(q,(user.name,user.email,0))
        db_con.commit()
        return {"status": "ok", "id": cur.lastrowid}
    except sqlite3.IntegrityError:
        db_con.rollback()
        raise HTTPException(status_code=409, detail="Bu e posta zaten kayıtlı")
    finally:
         cur.close()

@app.get("/user_search")
async def get_user(name: str):
    cur = db_con.cursor()


    q = "SELECT id, name FROM users WHERE name=?"
    cur.execute(q,(name,))
    res = cur.fetchall()
    return res

@app.get("/feed")
async def get_feed():
    cur = db_con.cursor()
  
    cur.execute("SELECT * FROM posts")
    all_p = cur.fetchall()

    post_ids = [p[0] for p in all_p]
    if not post_ids :
        cur.close()
        return[]

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

@app.get("/all_data")
async def all_data(filter_text: str = "", _: None = Depends(require_admin)):
    cur = db_con.cursor()
    cur.execute("SELECT id, name,email, is_admin FROM users")
    big_data = cur.fetchall()
    
    filtered = []
    for row in big_data:
        if filter_text in str(row):
            filtered.append(row)
            
    return filtered

@app.get("/export")
async def export(_: None = Depends(require_admin)):
    cur = db_con.cursor()
    
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
            
    return {"count": count}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
