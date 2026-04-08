from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

DB_NAME = "users.db"

# -----------------------------
# DATABASE INIT
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            x_benzene REAL NOT NULL,
            x_toluene REAL NOT NULL,
            temperature REAL NOT NULL,
            pressure REAL NOT NULL,
            y_benzene REAL NOT NULL,
            y_toluene REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            endpoint TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            email TEXT,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

init_db()

# -----------------------------
# HELPERS
# -----------------------------
def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr

def log_security(action, status="SUCCESS", user_id=None, username=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO security_logs (user_id, username, action, ip_address, user_agent, endpoint, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        username,
        action,
        get_client_ip(),
        request.headers.get("User-Agent"),
        request.path,
        status
    ))
    conn.commit()
    conn.close()

def is_blocked(ip_address, email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    ten_minutes_ago = datetime.now() - timedelta(minutes=10)

    c.execute("""
        SELECT COUNT(*) FROM login_attempts
        WHERE ip_address = ? AND email = ? AND attempt_time >= ?
    """, (ip_address, email, ten_minutes_ago.strftime("%Y-%m-%d %H:%M:%S")))

    count = c.fetchone()[0]
    conn.close()

    return count >= 5

def register_failed_attempt(ip_address, email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO login_attempts (ip_address, email)
        VALUES (?, ?)
    """, (ip_address, email))
    conn.commit()
    conn.close()

# -----------------------------
# LOGIN REQUIRED
# -----------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Veuillez vous connecter d'abord.", "warning")
            log_security("UNAUTHORIZED_ACCESS", status="BLOCKED")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# -----------------------------
# THERMO CALC
# -----------------------------
def calculate_thermo(x_benzene, x_toluene, pressure, temperature):
    total = x_benzene + x_toluene
    if round(total, 3) != 1.0:
        raise ValueError("La somme des fractions molaires doit être égale à 1.")

    alpha_benzene = 2.4
    y_benzene = (alpha_benzene * x_benzene) / (1 + (alpha_benzene - 1) * x_benzene)
    y_toluene = 1 - y_benzene

    return round(y_benzene, 4), round(y_toluene, 4)

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not username or not email or not password:
            flash("Tous les champs sont obligatoires.", "danger")
            log_security("REGISTER_FAILED_EMPTY_FIELDS", status="FAILED")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "danger")
            log_security("REGISTER_FAILED_WEAK_PASSWORD", status="FAILED")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                      (username, email, hashed_password))
            conn.commit()

            c.execute("SELECT id FROM users WHERE email = ?", (email,))
            new_user = c.fetchone()
            conn.close()

            log_security("REGISTER_SUCCESS", user_id=new_user[0], username=username)

            flash("Inscription réussie ! Connectez-vous maintenant.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Nom d'utilisateur ou email déjà utilisé.", "danger")
            log_security("REGISTER_FAILED_DUPLICATE", status="FAILED", username=username)
            return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        ip_address = get_client_ip()

        if is_blocked(ip_address, email):
            flash("Trop de tentatives. Réessayez dans 10 minutes.", "danger")
            log_security("LOGIN_BLOCKED_RATE_LIMIT", status="BLOCKED")
            return redirect(url_for("login"))

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT id, username, password FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            log_security("LOGIN_SUCCESS", user_id=user[0], username=user[1])
            flash("Connexion réussie.", "success")
            return redirect(url_for("dashboard"))
        else:
            register_failed_attempt(ip_address, email)
            log_security("LOGIN_FAILED", status="FAILED")
            flash("Email ou mot de passe incorrect.", "danger")

    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    result = None

    if request.method == "POST":
        try:
            x_benzene = float(request.form["benzene"])
            x_toluene = float(request.form["toluene"])
            temperature = float(request.form["temperature"])
            pressure = float(request.form["pressure"])

            y_benzene, y_toluene = calculate_thermo(
                x_benzene, x_toluene, pressure, temperature
            )

            result = {
                "x_benzene": x_benzene,
                "x_toluene": x_toluene,
                "temperature": temperature,
                "pressure": pressure,
                "y_benzene": y_benzene,
                "y_toluene": y_toluene
            }

            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("""
                INSERT INTO calculations (
                    user_id, x_benzene, x_toluene, temperature, pressure, y_benzene, y_toluene
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session["user_id"],
                x_benzene,
                x_toluene,
                temperature,
                pressure,
                y_benzene,
                y_toluene
            ))
            conn.commit()
            conn.close()

            log_security("THERMO_CALCULATION", user_id=session["user_id"], username=session["username"])
            flash("Calcul thermodynamique effectué avec succès.", "success")

        except ValueError as e:
            flash(str(e), "danger")
            log_security("THERMO_CALCULATION_FAILED", status="FAILED", user_id=session["user_id"], username=session["username"])
        except Exception:
            flash("Erreur lors du calcul. Vérifiez les valeurs saisies.", "danger")
            log_security("THERMO_CALCULATION_ERROR", status="FAILED", user_id=session["user_id"], username=session["username"])

    return render_template("dashboard.html", result=result)

@app.route("/history")
@login_required
def history():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            SELECT x_benzene, x_toluene, temperature, pressure, y_benzene, y_toluene, created_at
            FROM calculations
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (session["user_id"],))
        calculations = c.fetchall()
        conn.close()

        log_security("VIEW_HISTORY", user_id=session["user_id"], username=session["username"])
        return render_template("history.html", calculations=calculations)

    except sqlite3.OperationalError:
        flash("Erreur de base de données : veuillez réinitialiser users.db.", "danger")
        log_security("HISTORY_DB_ERROR", status="FAILED", user_id=session["user_id"], username=session["username"])
        return redirect(url_for("dashboard"))

@app.route("/security")
@login_required
def security():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT username, action, ip_address, endpoint, status, created_at
        FROM security_logs
        ORDER BY created_at DESC
        LIMIT 50
    """)
    logs = c.fetchall()

    c.execute("SELECT COUNT(*) FROM security_logs WHERE action = 'LOGIN_SUCCESS'")
    total_logins = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM security_logs WHERE action = 'THERMO_CALCULATION'")
    total_calculations = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM security_logs WHERE status = 'FAILED'")
    failed_events = c.fetchone()[0]

    conn.close()

    log_security("VIEW_SECURITY_DASHBOARD", user_id=session["user_id"], username=session["username"])

    return render_template(
        "security.html",
        logs=logs,
        total_logins=total_logins,
        total_calculations=total_calculations,
        failed_events=failed_events
    )

@app.route("/logout")
def logout():
    if "user_id" in session:
        log_security("LOGOUT", user_id=session.get("user_id"), username=session.get("username"))
    session.clear()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)