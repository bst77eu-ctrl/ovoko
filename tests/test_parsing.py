from pathlib import Path

import pytest

from app.extraction import (
    CHAMPS_NUMERIQUES,
    CHAMPS_TEXTE,
    analyser_reponse,
    extraction_vide,
)

FIXTURES = Path(__file__).parent / "fixtures" / "reponses_malformees"
CLES_SCHEMA = set(extraction_vide().keys())


def charger(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


def test_json_valide():
    extraction = analyser_reponse(charger("json_valide.txt"))
    assert extraction["instrument"] == "EURUSD"
    assert extraction["timeframe"] == "H1"
    assert extraction["prix_actuel"] == pytest.approx(1.0850)
    assert extraction["niveaux_horizontaux"] == [1.0800, 1.0900]
    assert extraction["indicateurs_visibles"] == ["EMA 200", "RSI"]
    assert extraction["tendance_visuelle"] == "haussiere"
    assert extraction["champs_illisibles"] == []
    assert extraction["fiabilite_lecture"] == pytest.approx(0.9)


def test_json_entoure_de_texte():
    extraction = analyser_reponse(charger("json_avec_texte_autour.txt"))
    assert extraction["instrument"] == "BTCUSD"
    assert extraction["prix_actuel"] == pytest.approx(43250.0)
    assert "plus_haut_visible" in extraction["champs_illisibles"]


def test_json_dans_code_fence():
    extraction = analyser_reponse(charger("json_dans_code_fence.txt"))
    assert extraction["instrument"] == "DAX"
    assert extraction["prix_actuel"] is None
    assert "prix_actuel" in extraction["champs_illisibles"]


def test_reponse_sans_json_donne_extraction_vide():
    extraction = analyser_reponse(charger("pas_de_json.txt"))
    assert extraction == extraction_vide()


def test_json_invalide_donne_extraction_vide():
    extraction = analyser_reponse(charger("json_invalide.txt"))
    assert extraction == extraction_vide()


def test_liste_json_donne_extraction_vide():
    extraction = analyser_reponse(charger("liste_json.txt"))
    assert extraction == extraction_vide()


def test_reponse_vide_donne_extraction_vide():
    assert analyser_reponse("") == extraction_vide()
    assert analyser_reponse("   ") == extraction_vide()


def test_champs_manquants_marques_illisibles():
    extraction = analyser_reponse(charger("champs_manquants.txt"))
    assert extraction["instrument"] == "EURUSD"
    attendus = set(CHAMPS_TEXTE + CHAMPS_NUMERIQUES) - {"instrument"}
    assert set(extraction["champs_illisibles"]) == attendus
    assert extraction["tendance_visuelle"] == "indeterminee"


def test_types_incorrects_jamais_devines():
    extraction = analyser_reponse(charger("types_incorrects.txt"))
    # instrument numérique → rejeté ; "environ 1.08" n'est pas un chiffre écrit
    assert extraction["instrument"] is None
    assert extraction["prix_actuel"] is None
    # une chaîne strictement numérique est acceptée
    assert extraction["plus_haut_visible"] == pytest.approx(1.0920)
    # un booléen n'est pas un prix
    assert extraction["plus_bas_visible"] is None
    assert extraction["niveaux_horizontaux"] == []
    assert extraction["indicateurs_visibles"] == ["RSI"]
    assert extraction["tendance_visuelle"] == "indeterminee"
    assert extraction["fiabilite_lecture"] == 0.0


def test_cles_interdites_supprimees():
    # Cœur de la contrainte : recommandations et prédictions injectées par
    # le modèle ne franchissent jamais la normalisation.
    extraction = analyser_reponse(charger("cle_interdite.txt"))
    assert set(extraction.keys()) == CLES_SCHEMA
    assert "recommandation" not in extraction
    assert "confiance_hausse" not in extraction
    assert "objectif_prix_prevu" not in extraction


def test_tendance_invalide_devient_indeterminee():
    extraction = analyser_reponse(charger("tendance_invalide.txt"))
    assert extraction["tendance_visuelle"] == "indeterminee"
    # fiabilité 1.7 → bornée à 1.0
    assert extraction["fiabilite_lecture"] == 1.0


def test_tendance_avec_accent_acceptee():
    extraction = analyser_reponse(
        '{"tendance_visuelle": "Haussière", "fiabilite_lecture": 0.5}'
    )
    assert extraction["tendance_visuelle"] == "haussiere"


def test_toutes_les_fixtures_donnent_le_schema_exact():
    for fixture in FIXTURES.glob("*.txt"):
        extraction = analyser_reponse(fixture.read_text(encoding="utf-8"))
        assert set(extraction.keys()) == CLES_SCHEMA, fixture.name
