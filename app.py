from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)

# 🔶 Création de la base de données
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS melange (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        x1 REAL,
        x2 REAL,
        resultat REAL
    )
    ''')

    conn.commit()
    conn.close()

# 🔶 Route principale
@app.route("/", methods=["GET", "POST"])
def index():
    resultat = None

    if request.method == "POST":
        try:
            x1 = float(request.form["x1"])
            x2 = float(request.form["x2"])

            # 🔥 Données de l'exercice
            P1 = 101.3
            P2 = 40

            # 🔥 Calcul pression de bulle
            resultat = x1 * P1 + x2 * P2

            # 🔶 Enregistrer dans la base
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO melange (x1, x2, resultat) VALUES (?, ?, ?)",
                (x1, x2, resultat)
            )

            conn.commit()
            conn.close()

        except:
            resultat = "Erreur dans les valeurs"

    return render_template("index.html", resultat=resultat)

# 🔶 Lancement
if __name__ == "__main__":
    init_db()  # ⚠️ crée la table automatiquement
    app.run(debug=True)
import os

import os

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))