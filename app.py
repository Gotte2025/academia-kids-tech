from flask import Flask, render_template, request, redirect, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret123"

# ------------------------
# BASE DE DATOS
# ------------------------
def get_db():
    return sqlite3.connect("database.db")

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        xp INTEGER,
        nivel INTEGER
    )
    """)
    conn.commit()
    conn.close()

# ------------------------
# LOGIN
# ------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
        result = c.fetchone()
        conn.close()

        if result:
            session["user"] = result[1]
            return redirect("/dashboard")

    return render_template("login.html")

# ------------------------
# DASHBOARD
# ------------------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT xp, nivel FROM users WHERE username=?", (session["user"],))
    data = c.fetchone()
    conn.close()

    return render_template("dashboard.html",
                           user=session["user"],
                           xp=data[0],
                           nivel=data[1])

# ------------------------
# ADMIN PRO
# ------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]

        c.execute("INSERT INTO users (username,password,xp,nivel) VALUES (?,?,0,1)",
                  (user, pw))
        conn.commit()

    c.execute("SELECT * FROM users")
    users = c.fetchall()
    conn.close()

    return render_template("admin.html", users=users)

# ------------------------
# SUMAR XP
# ------------------------
@app.route("/add_xp/<username>/<int:xp>")
def add_xp(username, xp):
    conn = get_db()
    c = conn.cursor()

    c.execute("UPDATE users SET xp = xp + ? WHERE username=?", (xp, username))

    # recalcular nivel automáticamente
    c.execute("SELECT xp FROM users WHERE username=?", (username,))
    total_xp = c.fetchone()[0]

    nivel = total_xp // 100 + 1
    c.execute("UPDATE users SET nivel=? WHERE username=?", (nivel, username))

    conn.commit()
    conn.close()

    return redirect("/admin")

# ------------------------
# RANKING
# ------------------------
@app.route("/ranking")
def ranking():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT username, xp, nivel FROM users ORDER BY xp DESC")
    users = c.fetchall()

    conn.close()

    return render_template("ranking.html", users=users)

# ------------------------
# MAIN (IMPORTANTE PARA RENDER)
# ------------------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)