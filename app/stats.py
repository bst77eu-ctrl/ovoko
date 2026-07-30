"""Statistiques du journal.

Winrate, gain/perte moyens, espérance, et surtout la corrélation entre
les réponses à la checklist et les résultats : pour chaque question, les
trades clôturés sont regroupés selon la réponse (oui/non) et comparés.
Aucune statistique n'est une prédiction — ce sont des mesures du passé.
"""

from __future__ import annotations


def _moyenne(valeurs: list[float]) -> float | None:
    return sum(valeurs) / len(valeurs) if valeurs else None


def _stats_groupe(trades: list[dict]) -> dict:
    resultats = [t["resultat_eur"] for t in trades]
    gagnants = [r for r in resultats if r > 0]
    return {
        "nombre": len(trades),
        "winrate": len(gagnants) / len(trades) if trades else None,
        "resultat_moyen": _moyenne(resultats),
    }


def calculer_stats(trades: list[dict], questions: list[dict]) -> dict:
    clotures = [t for t in trades if t.get("resultat_eur") is not None]
    resultats = [t["resultat_eur"] for t in clotures]
    gains = [r for r in resultats if r > 0]
    pertes = [r for r in resultats if r < 0]

    par_question = []
    for question in questions:
        identifiant = question["id"]
        oui = [t for t in clotures if t["checklist"].get(identifiant) is True]
        non = [t for t in clotures if t["checklist"].get(identifiant) is False]
        par_question.append(
            {
                "id": identifiant,
                "question": question["question"],
                "oui": _stats_groupe(oui),
                "non": _stats_groupe(non),
            }
        )

    return {
        "nombre_trades": len(trades),
        "nombre_clotures": len(clotures),
        "winrate": len(gains) / len(clotures) if clotures else None,
        "gain_moyen": _moyenne(gains),
        "perte_moyenne": _moyenne(pertes),
        "esperance": _moyenne(resultats),
        "par_question": par_question,
    }
