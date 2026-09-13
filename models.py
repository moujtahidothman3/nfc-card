from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Profile(db.Model):
    __tablename__ = "profiles"

    id        = db.Column(db.Integer, primary_key=True)
    username  = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)
    company   = db.Column(db.String(100), nullable=False)
    email     = db.Column(db.String(120), nullable=True)
    linkedin  = db.Column(db.String(100), nullable=True)
    photo_filename = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"<Profile {self.username}>"
