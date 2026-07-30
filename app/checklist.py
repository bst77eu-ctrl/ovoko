"""Module 3 — Checklist de pré-trade.

Les questions vivent dans un fichier YAML édité par l'utilisateur. Chaque
question appelle une réponse explicite oui/non ; l'enregistrement d'un
trade exige que TOUTES les questions aient une réponse (pas forcément
"oui" — c'est la corrélation réponses/résultats qui fait la valeur du
journal). Aucune case n'est jamais pré-cochée.
"""

from __future__ import annotations

import yaml


class ErreurChecklist(ValueError):
    """Checklist YAML invalide ou réponses incomplètes."""


def charger_checklist(chemin: str) -> list[dict]:
    """Charge et valide le YAML. Renvoie [{"id": ..., "question": ...}]."""
    try:
        with open(chemin, encoding="utf-8") as fichier:
            contenu = yaml.safe_load(fichier)
    except FileNotFoundError:
        raise ErreurChecklist(f"fichier de checklist introuvable : {chemin}") from None
    except yaml.YAMLError as erreur:
        raise ErreurChecklist(f"YAML invalide : {erreur}") from None

    if not isinstance(contenu, dict) or not isinstance(contenu.get("questions"), list):
        raise ErreurChecklist('le YAML doit contenir une liste "questions"')
    if not contenu["questions"]:
        raise ErreurChecklist("la checklist ne contient aucune question")

    questions = []
    identifiants = set()
    for element in contenu["questions"]:
        if not isinstance(element, dict):
            raise ErreurChecklist(f"entrée de checklist invalide : {element!r}")
        identifiant = element.get("id")
        question = element.get("question")
        if not isinstance(identifiant, str) or not identifiant.strip():
            raise ErreurChecklist(f"id manquant ou vide : {element!r}")
        if not isinstance(question, str) or not question.strip():
            raise ErreurChecklist(f"question manquante pour l'id {identifiant!r}")
        identifiant = identifiant.strip()
        if identifiant in identifiants:
            raise ErreurChecklist(f"id en double dans la checklist : {identifiant!r}")
        identifiants.add(identifiant)
        questions.append({"id": identifiant, "question": question.strip()})
    return questions


def valider_reponses(questions: list[dict], reponses: dict) -> dict[str, bool]:
    """Vérifie que chaque question a une réponse booléenne explicite.

    Lève ErreurChecklist si une question est sans réponse, si une réponse
    n'est pas un booléen strict, ou si une réponse ne correspond à aucune
    question connue.
    """
    if not isinstance(reponses, dict):
        raise ErreurChecklist("les réponses doivent être un objet {id: oui/non}")
    attendus = {q["id"] for q in questions}
    inconnus = set(reponses) - attendus
    if inconnus:
        raise ErreurChecklist(f"réponses pour des questions inconnues : {sorted(inconnus)}")
    manquants = attendus - set(reponses)
    if manquants:
        raise ErreurChecklist(
            f"questions sans réponse : {sorted(manquants)} — toutes les questions "
            "doivent recevoir une réponse explicite avant d'enregistrer le trade"
        )
    for identifiant, valeur in reponses.items():
        if not isinstance(valeur, bool):
            raise ErreurChecklist(
                f"réponse non booléenne pour {identifiant!r} : {valeur!r}"
            )
    return {q["id"]: reponses[q["id"]] for q in questions}
