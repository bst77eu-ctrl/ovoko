import pytest

from app.journal import ErreurJournal, Journal
from app.stats import calculer_stats

RISQUE = {
    "entrees": {"capital": 10_000, "risque_pct": 1, "prix_entree": 100, "stop_loss": 95},
    "sens": "long",
    "taille_position": 20.0,
    "risque_par_unite": 5.0,
    "perte_max": 100.0,
    "gain_potentiel": None,
    "ratio_risque_rendement": None,
}
EXTRACTION = {"instrument": "EURUSD", "timeframe": "H1"}


def nouveau_journal(tmp_path) -> Journal:
    return Journal(tmp_path / "data")


def test_enregistrement_et_lecture(tmp_path):
    journal = nouveau_journal(tmp_path)
    identifiant = journal.enregistrer_trade(
        extraction=EXTRACTION,
        checklist={"stop_place": True},
        risque=RISQUE,
        capture=b"fausse image png",
        capture_media_type="image/png",
    )
    trade = journal.obtenir_trade(identifiant)
    assert trade["extraction"]["instrument"] == "EURUSD"
    assert trade["checklist"] == {"stop_place": True}
    assert trade["risque"]["perte_max"] == 100.0
    assert trade["resultat_eur"] is None
    assert trade["resultat_r"] is None
    assert (journal.dossier_captures / trade["capture_chemin"]).read_bytes() == b"fausse image png"


def test_resultat_et_resultat_en_r(tmp_path):
    journal = nouveau_journal(tmp_path)
    identifiant = journal.enregistrer_trade(EXTRACTION, {"a": True}, RISQUE)
    journal.enregistrer_resultat(identifiant, -50)
    trade = journal.obtenir_trade(identifiant)
    assert trade["resultat_eur"] == -50.0
    assert trade["resultat_r"] == pytest.approx(-0.5)
    assert trade["cloture_horodatage"] is not None


def test_resultat_trade_inexistant(tmp_path):
    journal = nouveau_journal(tmp_path)
    with pytest.raises(ErreurJournal, match="introuvable"):
        journal.enregistrer_resultat(999, 10)


def test_resultat_non_numerique(tmp_path):
    journal = nouveau_journal(tmp_path)
    identifiant = journal.enregistrer_trade(EXTRACTION, {"a": True}, RISQUE)
    with pytest.raises(ErreurJournal, match="nombre"):
        journal.enregistrer_resultat(identifiant, "beaucoup")


def test_liste_ordre_recent_en_premier(tmp_path):
    journal = nouveau_journal(tmp_path)
    premier = journal.enregistrer_trade(EXTRACTION, {"a": True}, RISQUE)
    second = journal.enregistrer_trade(EXTRACTION, {"a": False}, RISQUE)
    trades = journal.lister_trades()
    assert [t["id"] for t in trades] == [second, premier]


QUESTIONS = [
    {"id": "stop_place", "question": "Stop placé ?"},
    {"id": "respect_plan", "question": "Plan respecté ?"},
]


def trade_clos(resultat, reponses):
    return {"resultat_eur": resultat, "checklist": reponses, "risque": RISQUE}


def test_stats_vides():
    stats = calculer_stats([], QUESTIONS)
    assert stats["nombre_trades"] == 0
    assert stats["winrate"] is None
    assert stats["gain_moyen"] is None


def test_stats_globales():
    trades = [
        trade_clos(100, {"stop_place": True, "respect_plan": True}),
        trade_clos(-50, {"stop_place": True, "respect_plan": False}),
        trade_clos(-150, {"stop_place": False, "respect_plan": False}),
        {"resultat_eur": None, "checklist": {}, "risque": RISQUE},  # encore ouvert
    ]
    stats = calculer_stats(trades, QUESTIONS)
    assert stats["nombre_trades"] == 4
    assert stats["nombre_clotures"] == 3
    assert stats["winrate"] == pytest.approx(1 / 3)
    assert stats["gain_moyen"] == pytest.approx(100.0)
    assert stats["perte_moyenne"] == pytest.approx(-100.0)
    assert stats["esperance"] == pytest.approx(-100 / 3)


def test_correlation_checklist_resultats():
    # La question "respect_plan" sépare nettement gagnants et perdants.
    trades = [
        trade_clos(100, {"stop_place": True, "respect_plan": True}),
        trade_clos(80, {"stop_place": False, "respect_plan": True}),
        trade_clos(-60, {"stop_place": True, "respect_plan": False}),
        trade_clos(-90, {"stop_place": False, "respect_plan": False}),
    ]
    stats = calculer_stats(trades, QUESTIONS)
    par_id = {q["id"]: q for q in stats["par_question"]}

    respect = par_id["respect_plan"]
    assert respect["oui"]["nombre"] == 2
    assert respect["oui"]["winrate"] == 1.0
    assert respect["non"]["winrate"] == 0.0
    assert respect["non"]["resultat_moyen"] == pytest.approx(-75.0)

    stop = par_id["stop_place"]
    assert stop["oui"]["winrate"] == 0.5
    assert stop["non"]["winrate"] == 0.5


def test_correlation_groupe_vide():
    trades = [trade_clos(100, {"stop_place": True, "respect_plan": True})]
    stats = calculer_stats(trades, QUESTIONS)
    respect = {q["id"]: q for q in stats["par_question"]}["respect_plan"]
    assert respect["non"]["nombre"] == 0
    assert respect["non"]["winrate"] is None
