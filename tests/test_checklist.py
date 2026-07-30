import pytest

from app.checklist import ErreurChecklist, charger_checklist, valider_reponses


def ecrire(tmp_path, contenu):
    chemin = tmp_path / "checklist.yaml"
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


def test_chargement_valide(tmp_path):
    chemin = ecrire(
        tmp_path,
        "questions:\n"
        "  - id: stop_place\n"
        '    question: "Mon stop est-il placé ?"\n'
        "  - id: respect_plan\n"
        '    question: "Est-ce que je respecte mon plan ?"\n',
    )
    questions = charger_checklist(chemin)
    assert [q["id"] for q in questions] == ["stop_place", "respect_plan"]


def test_fichier_absent(tmp_path):
    with pytest.raises(ErreurChecklist, match="introuvable"):
        charger_checklist(tmp_path / "absente.yaml")


def test_id_en_double(tmp_path):
    chemin = ecrire(
        tmp_path,
        "questions:\n"
        "  - {id: a, question: 'Q1 ?'}\n"
        "  - {id: a, question: 'Q2 ?'}\n",
    )
    with pytest.raises(ErreurChecklist, match="double"):
        charger_checklist(chemin)


def test_question_vide(tmp_path):
    chemin = ecrire(tmp_path, "questions:\n  - {id: a, question: ''}\n")
    with pytest.raises(ErreurChecklist, match="question"):
        charger_checklist(chemin)


def test_liste_vide(tmp_path):
    chemin = ecrire(tmp_path, "questions: []\n")
    with pytest.raises(ErreurChecklist, match="aucune question"):
        charger_checklist(chemin)


QUESTIONS = [{"id": "a", "question": "A ?"}, {"id": "b", "question": "B ?"}]


def test_reponses_completes():
    assert valider_reponses(QUESTIONS, {"a": True, "b": False}) == {
        "a": True,
        "b": False,
    }


def test_reponse_manquante_refusee():
    with pytest.raises(ErreurChecklist, match="sans réponse"):
        valider_reponses(QUESTIONS, {"a": True})


def test_reponse_non_booleenne_refusee():
    with pytest.raises(ErreurChecklist, match="booléenne"):
        valider_reponses(QUESTIONS, {"a": True, "b": "oui"})


def test_reponse_inconnue_refusee():
    with pytest.raises(ErreurChecklist, match="inconnues"):
        valider_reponses(QUESTIONS, {"a": True, "b": False, "c": True})
