"""
migrate_email_optional.py
---------------------------
Migration : rend la colonne 'email' optionnelle (NULL autorisé).

SQLite ne permet pas de modifier directement une contrainte NOT NULL
avec un simple ALTER TABLE. Il faut reconstruire la table :
  1. Créer une nouvelle table avec le bon schéma
  2. Copier toutes les données existantes dedans
  3. Supprimer l'ancienne table
  4. Renommer la nouvelle à la place de l'ancienne

Aucune donnée n'est perdue dans ce processus.

Utilisation :
    py migrate_email_optional.py
"""

import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "database.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Base de données introuvable à {DB_PATH}.")
        print("   Lance d'abord 'py app.py' une fois pour la créer.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Vérifie si la contrainte est déjà relâchée (colonne 'notnull' à 0)
    cursor.execute("PRAGMA table_info(profiles)")
    columns_info = cursor.fetchall()
    email_col = next((c for c in columns_info if c[1] == "email"), None)

    if email_col is not None and email_col[3] == 0:
        print("ℹ️  La colonne 'email' est déjà optionnelle. Rien à faire.")
        conn.close()
        return

    print("--- Migration : rendre 'email' optionnel ---")

    cursor.execute("""
        CREATE TABLE profiles_new (
            id INTEGER PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            job_title VARCHAR(100) NOT NULL,
            company VARCHAR(100) NOT NULL,
            email VARCHAR(120),
            linkedin VARCHAR(100),
            photo_filename VARCHAR(200)
        )
    """)

    cursor.execute("""
        INSERT INTO profiles_new (id, username, full_name, job_title, company, email, linkedin, photo_filename)
        SELECT id, username, full_name, job_title, company, email, linkedin, photo_filename
        FROM profiles
    """)

    cursor.execute("DROP TABLE profiles")
    cursor.execute("ALTER TABLE profiles_new RENAME TO profiles")

    conn.commit()
    print("✅ Colonne 'email' est maintenant optionnelle.")
    print("   Toutes les données existantes ont été préservées.")

    conn.close()


if __name__ == "__main__":
    migrate()
