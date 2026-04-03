from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# Configuration de la base de données SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -----------------------------
# MODELE DE LA BASE DE DONNEES
# -----------------------------
class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float, nullable=False)
    x1 = db.Column(db.Float, nullable=False)
    x2 = db.Column(db.Float, nullable=False)
    psat1 = db.Column(db.Float, nullable=False)
    psat2 = db.Column(db.Float, nullable=False)
    pbulle = db.Column(db.Float, nullable=False)
    y1 = db.Column(db.Float, nullable=False)
    y2 = db.Column(db.Float, nullable=False)

# -----------------------------
# FONCTION DE CALCUL
# -----------------------------
def calculate_bubble_pressure(x1, x2, psat1, psat2):
    pbulle = x1 * psat1 + x2 * psat2
    y1 = (x1 * psat1) / pbulle
    y2 = (x2 * psat2) / pbulle
    return pbulle, y1, y2

# -----------------------------
# PAGE PRINCIPALE
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        temperature = float(request.form["temperature"])
        x1 = float(request.form["x1"])
        x2 = float(request.form["x2"])
        psat1 = float(request.form["psat1"])
        psat2 = float(request.form["psat2"])

        # Vérification simple
        if round(x1 + x2, 3) != 1.0:
            return "Erreur : x1 + x2 doit être égal à 1"

        pbulle, y1, y2 = calculate_bubble_pressure(x1, x2, psat1, psat2)

        # Enregistrement dans la base de données
        new_exercise = Exercise(
            temperature=temperature,
            x1=x1,
            x2=x2,
            psat1=psat1,
            psat2=psat2,
            pbulle=pbulle,
            y1=y1,
            y2=y2
        )
        db.session.add(new_exercise)
        db.session.commit()

        return render_template(
            "result.html",
            temperature=temperature,
            x1=x1,
            x2=x2,
            psat1=psat1,
            psat2=psat2,
            pbulle=pbulle,
            y1=y1,
            y2=y2,
            somme=y1 + y2
        )

    return render_template("index.html")

# -----------------------------
# PAGE HISTORIQUE
# -----------------------------
@app.route("/history")
def history():
    exercises = Exercise.query.all()
    return render_template("history.html", exercises=exercises)

# -----------------------------
# CREATION DE LA BASE
# -----------------------------
with app.app_context():
    db.create_all()

# -----------------------------
# LANCEMENT APP
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)