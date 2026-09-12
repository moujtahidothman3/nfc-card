"""
migrate_add_photo.py
----------------------
Migration simple : ajoute la colonne 'photo_filename' à la table profiles
existante, SANS perdre les données déjà présentes.

À lancer UNE SEULE FOIS après avoir mis à jour models.py.

Utilisation :
    py migrate_add_photo.py
"""

import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "database.db")


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Base de données introuvable à {DB_PATH}.")
        print("   Lance d'abord 'py app.py' une fois pour la créer.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if column_exists(cursor, "profiles", "photo_filename"):
        print("ℹ️  La colonne 'photo_filename' existe déjà. Rien à faire.")
        conn.close()
        return

    print("--- Migration : ajout de la colonne 'photo_filename' ---")
    cursor.execute("ALTER TABLE profiles ADD COLUMN photo_filename VARCHAR(200)")
    conn.commit()
    print("✅ Colonne 'photo_filename' ajoutée avec succès.")
    print("   Les profils existants ont 'photo_filename' à NULL, c'est normal.")

    conn.close()


if __name__ == "__main__":
    migrate()
