import sqlite3
import time
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

db_con = sqlite3.connect('mulakat.db', check_same_thread=False)
cur = db_con.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, is_admin INTEGER)")
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

temp_state = []
req_count = 0

@app.post("/users")
async def create_user(req: Request):
    global req_count
    req_count += 1
    data1 = await req.json()
    x = data1["name"]
    y = data1["email"]
    z = data1.get("is_admin", 0)
    
    q = f"INSERT INTO users (name, email, is_admin) VALUES ('{x}', '{y}', {z})"
    cur.execute(q)
    db_con.commit()
    return {"status": "ok", "id": cur.lastrowid}

@app.get("/user_search")
async def get_user(name: str):
    global req_count
    req_count += 1
    
    q = f"SELECT * FROM users WHERE name='{name}'"
    cur.execute(q)
    res = cur.fetchall()
    return res

@app.get("/feed")
async def get_feed():
    global req_count
    req_count += 1
    time.sleep(1.5) 
    
    cur.execute("SELECT * FROM posts")
    all_p = cur.fetchall()
    
    temp_list = []
    for p in all_p:
        cur.execute(f"SELECT * FROM comments WHERE post_id={p[0]}")
        c = cur.fetchall()
        temp_list.append({"post_info": p, "comments": c})
        
    return temp_list

@app.get("/all_data")
async def all_data(filter_text: str = ""):
    cur.execute("SELECT * FROM users")
    big_data = cur.fetchall()
    
    filtered = []
    for row in big_data:
        if filter_text in str(row):
            filtered.append(row)
            
    return filtered

@app.get("/export")
async def export():
    s = ""
    cur.execute("SELECT * FROM users")
    d = cur.fetchall()
    
    for i in range(5000):
        for r in d:
            s += str(r) + " | " 
            
    return {"length": len(s)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
