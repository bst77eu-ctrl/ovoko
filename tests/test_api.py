import base64

import pytest
from fastapi.testclient import TestClient

from app import extraction as module_extraction
from app.main import creer_app

CHECKLIST_YAML = (
    "questions:\n"
    "  - {id: stop_place, question: 'Stop placé ?'}\n"
    "  - {id: respect_plan, question: 'Plan respecté ?'}\n"
)

CAPTURE = base64.b64encode(b"fausse image").decode()

RISQUE_VALIDE = {
    "capital": 10_000,
    "risque_pct": 1,
    "prix_entree": 100,
    "stop_loss": 95,
    "objectif": 110,
}


@pytest.fixture()
def client(tmp_path):
    chemin = tmp_path / "checklist.yaml"
    chemin.write_text(CHECKLIST_YAML, encoding="utf-8")
    application = creer_app(
        dossier_donnees=tmp_path / "data", chemin_checklist=chemin
    )
    return TestClient(application)


def test_checklist(client):
    reponse = client.get("/api/checklist")
    assert reponse.status_code == 200
    assert [q["id"] for q in reponse.json()["questions"]] == [
        "stop_place",
        "respect_plan",
    ]


def test_risque_valide(client):
    reponse = client.post("/api/risque", json=RISQUE_VALIDE)
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["sens"] == "long"
    assert corps["taille_position"] == pytest.approx(20.0)
    assert corps["ratio_risque_rendement"] == pytest.approx(2.0)


def test_risque_invalide_renvoie_400_en_francais(client):
    reponse = client.post(
        "/api/risque",
        json={"capital": 0, "risque_pct": 1, "prix_entree": 100, "stop_loss": 95},
    )
    assert reponse.status_code == 400
    assert "capital" in reponse.json()["detail"]


def _corps_trade(checklist):
    return {
        "capture_base64": CAPTURE,
        "capture_media_type": "image/png",
        "extraction": {"instrument": "EURUSD", "timeframe": "H1"},
        "checklist": checklist,
        "risque": RISQUE_VALIDE,
    }


def test_trade_refuse_si_checklist_incomplete(client):
    reponse = client.post("/api/trades", json=_corps_trade({"stop_place": True}))
    assert reponse.status_code == 400
    assert "sans réponse" in reponse.json()["detail"]


def test_trade_refuse_si_capture_invalide(client):
    corps = _corps_trade({"stop_place": True, "respect_plan": False})
    corps["capture_base64"] = "pas du base64 !!!"
    assert client.post("/api/trades", json=corps).status_code == 400


def test_flux_complet_trade_resultat_stats(client):
    # Enregistrement (un "non" dans la checklist est accepté)
    reponse = client.post(
        "/api/trades", json=_corps_trade({"stop_place": True, "respect_plan": False})
    )
    assert reponse.status_code == 201
    identifiant = reponse.json()["id"]

    # Le journal renvoie le trade, normalisé, encore ouvert
    trades = client.get("/api/trades").json()["trades"]
    assert len(trades) == 1
    assert trades[0]["extraction"]["instrument"] == "EURUSD"
    assert trades[0]["resultat_eur"] is None

    # Saisie du résultat après clôture
    reponse = client.post(
        f"/api/trades/{identifiant}/resultat", json={"resultat_eur": -100}
    )
    assert reponse.status_code == 200
    assert reponse.json()["trade"]["resultat_r"] == pytest.approx(-1.0)

    # Les statistiques reflètent le trade perdant et la case non respectée
    stats = client.get("/api/stats").json()
    assert stats["nombre_clotures"] == 1
    assert stats["winrate"] == 0.0
    par_id = {q["id"]: q for q in stats["par_question"]}
    assert par_id["respect_plan"]["non"]["nombre"] == 1
    assert par_id["respect_plan"]["non"]["winrate"] == 0.0


def test_resultat_trade_inexistant(client):
    assert (
        client.post("/api/trades/999/resultat", json={"resultat_eur": 5}).status_code
        == 404
    )


def test_extraction_avec_modele_simule(client, monkeypatch):
    # L'appel réseau est remplacé : on vérifie le câblage endpoint → parsing.
    monkeypatch.setattr(
        module_extraction,
        "appeler_claude",
        lambda image_base64, media_type: '{"instrument": "EURUSD", "fiabilite_lecture": 0.4}',
    )
    reponse = client.post(
        "/api/extraction",
        json={"image_base64": CAPTURE, "media_type": "image/png"},
    )
    assert reponse.status_code == 200
    extraction = reponse.json()["extraction"]
    assert extraction["instrument"] == "EURUSD"
    assert "prix_actuel" in extraction["champs_illisibles"]


def test_extraction_type_image_refuse(client):
    reponse = client.post(
        "/api/extraction",
        json={"image_base64": CAPTURE, "media_type": "application/pdf"},
    )
    assert reponse.status_code == 400
