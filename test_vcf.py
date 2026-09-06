"""
test_vcf.py
-----------
Test unitaire simple pour vérifier que la route /p/<username>/vcf
retourne bien un fichier .vcf valide avec le bon contenu.

Utilisation :
    py test_vcf.py
"""

from app import app


def test_vcard_download():
    client = app.test_client()
    resp = client.get("/p/othman/vcf")

    # --- Vérifications sur la réponse HTTP ---
    assert resp.status_code == 200, "La route devrait répondre 200"
    assert "text/vcard" in resp.headers.get("Content-Type", ""), \
        "Le Content-Type devrait être text/vcard"
    assert 'filename="othman.vcf"' in resp.headers.get("Content-Disposition", ""), \
        "Le nom de fichier attendu est othman.vcf"

    # --- Vérifications sur le contenu de la vCard ---
    content = resp.data.decode()
    assert content.startswith("BEGIN:VCARD"), "La vCard doit commencer par BEGIN:VCARD"
    assert content.rstrip().endswith("END:VCARD"), "La vCard doit se terminer par END:VCARD"
    assert "VERSION:3.0" in content
    assert "FN:Othman Moujtahid" in content
    assert "ORG:ABC Consulting" in content
    assert "TITLE:Consultant" in content
    assert "EMAIL:othman@abc.ma" in content
    assert "N:Moujtahid;Othman;;;" in content

    print("✅ test_vcard_download : OK")


def test_vcard_404_for_unknown_username():
    client = app.test_client()
    resp = client.get("/p/inconnu/vcf")

    assert resp.status_code == 404, "Un username inexistant doit retourner 404"

    print("✅ test_vcard_404_for_unknown_username : OK")


if __name__ == "__main__":
    test_vcard_download()
    test_vcard_404_for_unknown_username()
    print("\nTous les tests sont passés 🎉")
