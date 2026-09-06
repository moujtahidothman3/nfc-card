"""
seed.py
-------
Script d'insertion de profils de test dans la base de données.
Peut être relancé plusieurs fois sans créer de doublons
(vérification sur le champ 'username' avant chaque insertion).

Utilisation :
    py seed.py
"""

from app import app
from models import db, Profile

# Liste des profils de test à insérer
PROFILES_TO_SEED = [
    {
        "username": "othman",
        "full_name": "Othman Moujtahid",
        "job_title": "Consultant",
        "company": "ABC Consulting",
        "email": "othman@abc.ma",
        "linkedin": "othman-moujtahid",
    },
    {
        "username": "mohamed",
        "full_name": "Mohamed Alaoui",
        "job_title": "Commercial",
        "company": "XYZ SARL",
        "email": "mohamed@xyz.ma",
        "linkedin": "mohamed-alaoui",
    },
    {
        "username": "sarah",
        "full_name": "Sarah Benali",
        "job_title": "Avocate",
        "company": "Cabinet Benali",
        "email": "sarah@benali.ma",
        "linkedin": "sarah-benali",
    },
]


def seed_profiles():
    with app.app_context():
        print("--- Insertion des profils de test ---\n")

        for data in PROFILES_TO_SEED:
            existing = Profile.query.filter_by(username=data["username"]).first()

            if existing:
                # Si le profil existe déjà mais n'a pas encore de LinkedIn
                # (ex: créé avant l'ajout de ce champ), on le complète.
                if not existing.linkedin:
                    existing.linkedin = data["linkedin"]
                    db.session.commit()
                    print(f"↻  '{data['username']}' existe déjà, LinkedIn ajouté.")
                else:
                    print(f"⚠️  '{data['username']}' existe déjà, ignoré.")
                continue

            profile = Profile(
                username=data["username"],
                full_name=data["full_name"],
                job_title=data["job_title"],
                company=data["company"],
                email=data["email"],
                linkedin=data["linkedin"],
            )
            db.session.add(profile)
            db.session.commit()
            print(f"✅ Profil créé : {data['username']} ({data['full_name']})")

        print("\n--- Vérification finale ---")
        total = Profile.query.count()
        print(f"Nombre total de profils dans la base : {total}\n")

        print("Liste des profils présents :")
        for p in Profile.query.all():
            print(f"  - {p.username} | {p.full_name}")


if __name__ == "__main__":
    seed_profiles()
