from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
import mercadopago

app = Flask(__name__)
app.secret_key = "secret123"

sdk = mercadopago.SDK("TU_ACCESS_TOKEN")
RESET_KEY = "1234"

# ------------------------
# DB
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
        nivel INTEGER,
        clases INTEGER DEFAULT 0
    )
    """)

    # TABLA PAGOS 💰
    c.execute("""
    CREATE TABLE IF NOT EXISTS pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        pack INTEGER,
        monto INTEGER,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# ------------------------
# LOGIN
# ------------------------
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user,pw))
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
    c.execute("SELECT xp, nivel, clases FROM users WHERE username=?", (session["user"],))
    data = c.fetchone()
    conn.close()

    if data[2] <= 0:
        return render_template("pago.html", user=session["user"])

    return render_template("dashboard.html",
                           user=session["user"],
                           xp=data[0],
                           nivel=data[1],
                           clases=data[2])

# ------------------------
# ADMIN
# ------------------------
@app.route("/admin", methods=["GET","POST"])
def admin():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]

        c.execute("INSERT INTO users (username,password,xp,nivel,clases) VALUES (?,?,0,1,0)",
                  (user,pw))
        conn.commit()

    c.execute("SELECT * FROM users")
    users = c.fetchall()
    conn.close()

    return render_template("admin.html", users=users)

# ------------------------
# XP + USO DE CLASE
# ------------------------
@app.route("/add_xp/<username>/<int:xp>")
def add_xp(username, xp):
    conn = get_db()
    c = conn.cursor()

    c.execute("UPDATE users SET xp = xp + ? WHERE username=?", (xp, username))
    c.execute("UPDATE users SET clases = clases - 1 WHERE username=? AND clases > 0", (username,))

    c.execute("SELECT xp FROM users WHERE username=?", (username,))
    total_xp = c.fetchone()[0]

    nivel = total_xp // 100 + 1
    c.execute("UPDATE users SET nivel=? WHERE username=?", (nivel, username))

    conn.commit()
    conn.close()

    return redirect("/admin")

# ------------------------
# RESET TOTAL
# ------------------------
@app.route("/reset")
def reset():
    if request.args.get("key") != RESET_KEY:
        return "❌ Acceso denegado"

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM sqlite_sequence WHERE name='users'")
    conn.commit()
    conn.close()

    return "✅ Base limpia"

# ------------------------
# RESET USER
# ------------------------
@app.route("/reset_user/<username>")
def reset_user(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET xp=0, nivel=1, clases=0 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return redirect("/admin")

# ------------------------
# PAGOS PACK
# ------------------------
@app.route("/pagar/<username>/<int:pack>")
def pagar(username, pack):

    if pack == 1:
        precio = 3000
    elif pack == 4:
        precio = 10000
    elif pack == 16:
        precio = 35000
    else:
        return "Error pack"

    preference_data = {
        "items": [
            {
                "title": f"Pack {pack} clases - {username}",
                "quantity": 1,
                "unit_price": precio
            }
        ],
        "metadata": {
            "username": username,
            "clases": pack
        }
    }

    preference = sdk.preference().create(preference_data)
    return redirect(preference["response"]["init_point"])

# ------------------------
# WEBHOOK
# ------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if data.get("type") == "payment":
        payment_id = data["data"]["id"]

        payment = sdk.payment().get(payment_id)
        info = payment["response"]

        if info["status"] == "approved":
            username = info["metadata"]["username"]
            clases = info["metadata"]["clases"]

            if clases == 1:
                monto = 3000
            elif clases == 4:
                monto = 10000
            elif clases == 16:
                monto = 35000
            else:
                monto = 0

            conn = get_db()
            c = conn.cursor()

            c.execute("UPDATE users SET clases = clases + ? WHERE username=?", (clases, username))

            # guardar pago 💰
            c.execute("INSERT INTO pagos (username, pack, monto) VALUES (?, ?, ?)",
                      (username, clases, monto))

            conn.commit()
            conn.close()

    return "OK"

# ------------------------
# RANKING
# ------------------------
@app.route("/ranking")
def ranking():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT username, xp FROM users ORDER BY xp DESC")
    users = c.fetchall()
    conn.close()

    return render_template("ranking.html", users=users)

# ------------------------
# FINANZAS 💰
# ------------------------
@app.route("/finanzas")
def finanzas():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT SUM(monto) FROM pagos")
    total = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(*) FROM pagos")
    cantidad = c.fetchone()[0]

    c.execute("SELECT pack, COUNT(*) FROM pagos GROUP BY pack")
    packs = c.fetchall()

    c.execute("SELECT username, pack, monto, fecha FROM pagos ORDER BY fecha DESC")
    historial = c.fetchall()

    conn.close()

    return render_template("finanzas.html",
                           total=total,
                           cantidad=cantidad,
                           packs=packs,
                           historial=historial)

# ------------------------
# MAIN
# ------------------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)