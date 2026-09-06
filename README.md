# Cartes de visite NFC

Application Flask permettant de créer des cartes de visite numériques accessibles
via un lien public (`/p/<username>`), pensées pour être ouvertes en scannant un
tag NFC ou un QR Code. Chaque carte affiche le nom, la fonction, l'entreprise,
un lien LinkedIn optionnel, un bouton pour enregistrer le contact (`.vcf`),
et un QR Code de partage.

## Fonctionnalités

- Page profil publique mobile-first : `/p/<username>`
- Téléchargement du contact au format vCard (`.vcf`)
- QR Code généré à la volée (aucun fichier stocké sur le disque)
- Lien LinkedIn cliquable (optionnel)
- Interface d'administration (`/admin`) : créer, modifier, supprimer des profils
  sans toucher au code

## Stack technique

- **Flask** — framework web
- **Flask-SQLAlchemy** — ORM pour la base de données
- **SQLite** — base de données (fichier `instance/database.db`)
- **Segno** — génération de QR Codes (sans dépendance externe)
- **Gunicorn** — serveur de production

## Installation en local

**Prérequis** : Python 3.10+ installé sur ta machine.

1. Cloner ou télécharger ce dépôt, puis se placer dans le dossier du projet :
   ```bash
   cd nfc-card
   ```

2. Installer les dépendances :
   ```bash
   py -m pip install -r requirements.txt
   ```
   (sur Mac/Linux, remplace `py` par `python3`)

3. Lancer l'application :
   ```bash
   py app.py
   ```

4. Ouvrir dans le navigateur :
   - `http://127.0.0.1:5000/` — vérifie que le serveur tourne
   - `http://127.0.0.1:5000/admin` — gérer les profils
   - `http://127.0.0.1:5000/p/othman` — voir un exemple de carte (si le profil existe)

5. (Optionnel) Insérer des profils de test :
   ```bash
   py seed.py
   ```

## Structure du projet

```
nfc-card/
  app.py                       application Flask principale
  models.py                    modèle Profile (SQLAlchemy)
  seed.py                      script d'insertion de profils de test
  migrate_add_linkedin.py      migration ponctuelle (déjà appliquée)
  requirements.txt             dépendances Python
  templates/
    profile.html               page profil publique
    404.html                   page d'erreur
    admin/                     interface d'administration
  static/
    style.css                  style de la page profil
    admin.css                  style de l'interface admin
  instance/
    database.db                base de données SQLite (créée automatiquement)
```

## Déploiement en production

Voir la conversation de développement pour le guide détaillé pas à pas
(création du compte hébergeur, connexion à GitHub, configuration du service).

En résumé :
- **Build command** : `pip install -r requirements.txt`
- **Start command** : `gunicorn app:app`

⚠️ **Important — persistance des données** : sur la plupart des hébergeurs
gratuits, le système de fichiers est éphémère. La base `database.db` peut être
réinitialisée à chaque redéploiement. Voir la section "Limites du plan gratuit"
de la documentation du projet pour les options (disque persistant payant,
migration vers PostgreSQL, ou simplement relancer `seed.py` / recréer les
profils via `/admin` après chaque redéploiement).

## Sécurité — à faire avant un vrai lancement public

- [ ] Ajouter une authentification sur `/admin` (actuellement non protégée)
- [ ] Définir une vraie valeur pour `SECRET_KEY` via une variable d'environnement
- [ ] Envisager un disque persistant ou PostgreSQL si le nombre de profils grandit
