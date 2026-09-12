import os
import re
import unicodedata
import uuid
from io import BytesIO

import segno
from werkzeug.utils import secure_filename
from flask import (
    Flask,
    render_template,
    abort,
    Response,
    request,
    redirect,
    url_for,
    flash,
)
from models import db, Profile

# Chemin absolu vers le dossier instance/ pour éviter les surprises
# selon l'endroit d'où le script est lancé.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

DB_PATH = os.path.join(INSTANCE_DIR, "database.db")

# Dossier où sont stockées les photos de profil uploadées.
# ATTENTION : sur un hébergeur gratuit comme Render, ce dossier est
# effacé à chaque redéploiement (même limitation que la base SQLite).
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# Limite la taille max d'un fichier envoyé à 5 Mo, pour éviter qu'une
# photo énorme (ou un envoi malveillant) ne sature le serveur.
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# Nécessaire pour que flash() fonctionne (signe les messages stockés
# temporairement côté client dans un cookie de session).
# En MVP local, une valeur fixe suffit ; à remplacer par une vraie
# variable d'environnement avant une mise en production.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# Lien Regex basique pour valider un format d'email (suffisant pour un MVP,
# pas une validation RFC complète).
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Lier SQLAlchemy à l'application
db.init_app(app)

# Créer la table (et la base si elle n'existe pas encore)
with app.app_context():
    db.create_all()


def build_vcard(profile):
    """
    Construit le contenu texte d'une vCard (version 3.0) à partir d'un Profile.
    La ligne N: attend l'ordre : Nom de famille;Prénom;;;
    On déduit ces deux parties depuis full_name : le dernier mot est
    considéré comme le nom de famille, le reste comme le(s) prénom(s).
    """
    name_parts = profile.full_name.strip().split(" ")
    if len(name_parts) > 1:
        first_name = " ".join(name_parts[:-1])
        last_name = name_parts[-1]
    else:
        first_name = profile.full_name
        last_name = ""

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{last_name};{first_name};;;",
        f"FN:{profile.full_name}",
        f"ORG:{profile.company}",
        f"TITLE:{profile.job_title}",
        f"EMAIL:{profile.email}",
    ]

    if profile.linkedin:
        lines.append(f"URL:https://www.linkedin.com/in/{profile.linkedin}")

    lines.append("END:VCARD")

    # La spec vCard demande des fins de ligne CRLF
    return "\r\n".join(lines) + "\r\n"


def generate_qr_png(data, size=200):
    """
    Génère un QR Code (noir sur blanc) en PNG, entièrement en mémoire
    (aucun fichier écrit sur le disque).

    'size' est une taille cible approximative en pixels. Comme un QR Code
    est fait de "modules" carrés, segno construit l'image par multiples
    entiers (scale) : le résultat est donc le multiple le plus proche de
    la taille demandée, jamais une valeur floue par redimensionnement.
    """
    qr = segno.make(data)

    # Taille d'un module à l'échelle 1, bordure incluse (quiet zone = 4 modules,
    # recommandée par la norme QR pour rester scannable).
    base_width, _ = qr.symbol_size(scale=1, border=4)
    scale = max(1, round(size / base_width))

    buffer = BytesIO()
    qr.save(buffer, kind="png", scale=scale, border=4, dark="black", light="white")
    buffer.seek(0)
    return buffer


def allowed_photo(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS
    )


def save_uploaded_photo(file_storage):
    """
    Sauvegarde une photo uploadée sur le disque avec un nom de fichier
    unique (pour éviter tout conflit entre profils), et retourne le nom
    de fichier à stocker en base. Retourne None si aucun fichier valide
    n'a été fourni.
    """
    if not file_storage or file_storage.filename == "":
        return None

    if not allowed_photo(file_storage.filename):
        return None

    extension = file_storage.filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{extension}"
    safe_name = secure_filename(unique_name)

    file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], safe_name))
    return safe_name


def delete_photo_file(filename):
    """Supprime un fichier photo du disque s'il existe, sans jamais planter."""
    if not filename:
        return
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(path):
        os.remove(path)


def clean_linkedin_username(raw_value):
    """
    Nettoie une saisie LinkedIn quelconque pour n'en garder que le username.
    Utilise uniquement des méthodes de chaînes simples (pas de regex).

    Gère ces cas :
      "https://www.linkedin.com/in/othman-moujtahid/" -> "othman-moujtahid"
      "https://linkedin.com/in/othman-moujtahid"       -> "othman-moujtahid"
      "@othman-moujtahid"                              -> "othman-moujtahid"
      "  othman-moujtahid  "                           -> "othman-moujtahid"
      "" ou None                                        -> None
    """
    if not raw_value:
        return None

    value = raw_value.strip()
    if not value:
        return None

    # Retirer un éventuel "@" placé devant (ex: quelqu'un copie "@othman-moujtahid")
    if value.startswith("@"):
        value = value[1:]

    # Si c'est une URL LinkedIn, ne garder que ce qu'il y a après "/in/"
    if "linkedin.com/in/" in value:
        value = value.split("linkedin.com/in/", 1)[1]

    # Retirer d'éventuels paramètres d'URL après le username (ex: "?param=1")
    value = value.split("?", 1)[0]

    # Retirer un éventuel slash final (ex: ".../in/othman-moujtahid/")
    value = value.strip("/")

    value = value.strip()
    return value or None


def validate_profile_form(form_data, editing_id=None):
    """
    Valide les données d'un formulaire de profil (création ou édition).
    Retourne un message d'erreur (str) si un problème est trouvé,
    ou None si tout est valide.

    'editing_id' est l'id du profil en cours de modification (pour exclure
    ce profil lui-même de la vérification d'unicité du username), ou None
    lors d'une création.
    """
    username = form_data["username"]
    full_name = form_data["full_name"]
    job_title = form_data["job_title"]
    company = form_data["company"]
    email = form_data["email"]

    if not username or not full_name or not job_title or not company or not email:
        return "Tous les champs sont obligatoires."

    if not EMAIL_REGEX.match(email):
        return "L'adresse email n'est pas valide."

    existing = Profile.query.filter_by(username=username).first()
    if existing and existing.id != editing_id:
        return "Ce nom d'utilisateur existe déjà."

    return None


def clean_username(raw_username):
    """
    Nettoie un username saisi par un humain :
    - passage en minuscules
    - suppression de tous les espaces (début, fin, milieu)
    """
    return re.sub(r"\s+", "", raw_username.strip().lower())


def slugify_full_name(full_name):
    """
    Transforme un nom complet en une base de username simple :
    minuscules, sans accents, sans espaces ni caractères spéciaux.
    Ex : "Othman Bennani" -> "othmanbennani"
         "Léa Ané"        -> "leaane"
    """
    normalized = unicodedata.normalize("NFKD", full_name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "", ascii_only.lower())
    return slug or "profil"


def generate_unique_username(full_name, editing_id=None):
    """
    Génère un username unique à partir d'un nom complet.
    Si la base est déjà prise, ajoute un suffixe numérique (2, 3, ...)
    jusqu'à trouver une valeur libre.
    'editing_id' permet d'ignorer le profil en cours d'édition lui-même.
    """
    base = slugify_full_name(full_name)
    candidate = base
    suffix = 2

    while True:
        existing = Profile.query.filter_by(username=candidate).first()
        if existing is None or existing.id == editing_id:
            return candidate
        candidate = f"{base}{suffix}"
        suffix += 1


@app.route("/")
def index():
    return 'Serveur OK — <a href="/admin">Administration</a>'


@app.route("/check")
def check():
    profiles = Profile.query.all()

    if not profiles:
        return "Aucun profil trouvé dans la base."

    lines = [f"{p.id}. {p.username} - {p.full_name} ({p.job_title}, {p.company}) - {p.email}"
             for p in profiles]

    header = f"{len(profiles)} profil(s) trouvé(s) :\n\n"
    return header + "\n".join(lines), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/p/<username>")
def public_profile(username):
    profile = Profile.query.filter_by(username=username).first()

    if profile is None:
        abort(404)

    return render_template("profile.html", profile=profile)


@app.route("/p/<username>/vcf")
def download_vcard(username):
    profile = Profile.query.filter_by(username=username).first()

    if profile is None:
        abort(404)

    vcard_content = build_vcard(profile)

    return Response(
        vcard_content,
        mimetype="text/vcard",
        headers={
            "Content-Disposition": f'attachment; filename="{profile.username}.vcf"'
        },
    )


@app.route("/p/<username>/qrcode")
def profile_qrcode(username):
    profile = Profile.query.filter_by(username=username).first()

    if profile is None:
        abort(404)

    size = request.args.get("size", 200, type=int)
    profile_url = request.host_url + f"p/{profile.username}"

    png_buffer = generate_qr_png(profile_url, size=size)

    return Response(png_buffer.getvalue(), mimetype="image/png")


@app.route("/p/<username>/qrcode/download")
def download_qrcode(username):
    profile = Profile.query.filter_by(username=username).first()

    if profile is None:
        abort(404)

    size = request.args.get("size", 200, type=int)
    profile_url = request.host_url + f"p/{profile.username}"

    png_buffer = generate_qr_png(profile_url, size=size)

    return Response(
        png_buffer.getvalue(),
        mimetype="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{profile.username}-qrcode.png"'
        },
    )


@app.route("/admin")
def admin_list():
    profiles = Profile.query.order_by(Profile.id).all()
    return render_template("admin/list.html", profiles=profiles)


@app.route("/admin/create", methods=["GET", "POST"])
def admin_create():
    if request.method == "GET":
        # Formulaire vide, mode création
        return render_template("admin/form.html", profile=None, form_data={})

    # --- Traitement du formulaire (POST) ---
    form_data = {
        "username": request.form.get("username", ""),
        "full_name": request.form.get("full_name", "").strip(),
        "job_title": request.form.get("job_title", "").strip(),
        "company": request.form.get("company", "").strip(),
        "email": request.form.get("email", "").strip(),
        "linkedin": request.form.get("linkedin", ""),
    }

    if not form_data["full_name"] or not form_data["job_title"] or not form_data["company"] or not form_data["email"]:
        flash("Tous les champs sont obligatoires.", "error")
        return render_template("admin/form.html", profile=None, form_data=form_data)

    raw_username = form_data["username"].strip()
    if raw_username:
        username = clean_username(raw_username)
    else:
        username = generate_unique_username(form_data["full_name"], editing_id=None)

    form_data["username"] = username  # pour ré-affichage propre en cas d'erreur

    linkedin_username = clean_linkedin_username(form_data["linkedin"])
    form_data["linkedin"] = linkedin_username or ""

    error = validate_profile_form(form_data, editing_id=None)
    if error:
        flash(error, "error")
        return render_template("admin/form.html", profile=None, form_data=form_data)

    profile = Profile(
        username=username,
        full_name=form_data["full_name"],
        job_title=form_data["job_title"],
        company=form_data["company"],
        email=form_data["email"],
        linkedin=linkedin_username,
        photo_filename=save_uploaded_photo(request.files.get("photo")),
    )
    db.session.add(profile)
    db.session.commit()

    flash("Profil créé", "success")
    return redirect(url_for("admin_list"))


@app.route("/admin/<int:profile_id>/edit", methods=["GET", "POST"])
def admin_edit(profile_id):
    profile = Profile.query.get_or_404(profile_id)

    if request.method == "GET":
        form_data = {
            "username": profile.username,
            "full_name": profile.full_name,
            "job_title": profile.job_title,
            "company": profile.company,
            "email": profile.email,
            "linkedin": profile.linkedin or "",
        }
        return render_template("admin/form.html", profile=profile, form_data=form_data)

    # --- Traitement du formulaire (POST) ---
    form_data = {
        "username": request.form.get("username", ""),
        "full_name": request.form.get("full_name", "").strip(),
        "job_title": request.form.get("job_title", "").strip(),
        "company": request.form.get("company", "").strip(),
        "email": request.form.get("email", "").strip(),
        "linkedin": request.form.get("linkedin", ""),
    }

    if not form_data["full_name"] or not form_data["job_title"] or not form_data["company"] or not form_data["email"]:
        flash("Tous les champs sont obligatoires.", "error")
        return render_template("admin/form.html", profile=profile, form_data=form_data)

    raw_username = form_data["username"].strip()
    if raw_username:
        username = clean_username(raw_username)
    else:
        username = generate_unique_username(form_data["full_name"], editing_id=profile.id)

    form_data["username"] = username

    linkedin_username = clean_linkedin_username(form_data["linkedin"])
    form_data["linkedin"] = linkedin_username or ""

    error = validate_profile_form(form_data, editing_id=profile.id)
    if error:
        flash(error, "error")
        return render_template("admin/form.html", profile=profile, form_data=form_data)

    profile.username = username
    profile.full_name = form_data["full_name"]
    profile.job_title = form_data["job_title"]
    profile.company = form_data["company"]
    profile.email = form_data["email"]
    profile.linkedin = linkedin_username

    if request.form.get("remove_photo") == "1":
        # La personne a coché "Supprimer la photo actuelle"
        delete_photo_file(profile.photo_filename)
        profile.photo_filename = None
    else:
        new_photo_filename = save_uploaded_photo(request.files.get("photo"))
        if new_photo_filename:
            # Une nouvelle photo a été envoyée : on remplace l'ancienne
            delete_photo_file(profile.photo_filename)
            profile.photo_filename = new_photo_filename
        # Sinon : aucun changement, on garde la photo existante telle quelle

    db.session.commit()

    flash("Profil modifié", "success")
    return redirect(url_for("admin_list"))


@app.route("/admin/<int:profile_id>/delete", methods=["GET", "POST"])
def admin_delete(profile_id):
    profile = Profile.query.get_or_404(profile_id)

    if request.method == "GET":
        # Simple page de confirmation avant l'action réelle
        return render_template("admin/confirm_delete.html", profile=profile)

    # --- Suppression réelle (POST uniquement) ---
    delete_photo_file(profile.photo_filename)
    db.session.delete(profile)
    db.session.commit()

    flash("Profil supprimé", "success")
    return redirect(url_for("admin_list"))


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    # Ce bloc n'est utilisé QUE quand on lance "py app.py" directement (développement local).
    # En production, gunicorn importe directement l'objet "app" et n'exécute jamais ce bloc,
    # donc debug=True ici n'est jamais actif sur le serveur en ligne.
    #
    # FLASK_DEBUG=false peut être positionné en local si besoin de désactiver le débogueur.
    debug_mode = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
