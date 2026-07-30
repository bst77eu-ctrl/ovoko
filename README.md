# Assistant de pré-trade avec analyse de capture d'écran

> **Outil d'aide à la discipline. Aucune recommandation d'investissement.**

## Contrainte absolue

Cet outil ne produit **jamais** :
- de signal d'achat ou de vente,
- de prédiction de direction de prix,
- de score de confiance sur un résultat futur.

Toute information non déterminable depuis l'image est traitée comme
« non déterminable depuis une image ». Cette contrainte est le cœur du
projet.

## État d'avancement

- ✅ **Module 2 — Calcul de risque** (`app/risque.py`) : déterministe,
  sans IA, testé unitairement.
- ⏳ Modules 1 (extraction vision), 3 (checklist) et 4 (journal) : en
  attente de validation de l'arborescence ci-dessous.

## Arborescence proposée (en attente de validation)

```
ovoko/
├── README.md
├── requirements.txt
├── pyproject.toml             # config pytest
├── .env.example               # ANTHROPIC_API_KEY=...
├── checklist.yaml             # questions de pré-trade, éditées par l'utilisateur
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI : routes + service du frontend
│   ├── risque.py              # Module 2 — calcul déterministe (fait)
│   ├── extraction.py          # Module 1 — appel Claude vision + parsing JSON strict
│   ├── checklist.py           # Module 3 — chargement/validation du YAML
│   ├── journal.py             # Module 4 — SQLite (trades, captures, résultats)
│   └── stats.py               # statistiques + corrélation checklist/pertes
├── static/
│   └── index.html             # frontend une page (collage Ctrl+V, champs éditables)
├── tests/
│   ├── test_risque.py         # (fait)
│   ├── test_parsing.py        # réponses malformées en fixtures
│   └── fixtures/
│       └── reponses_malformees/
├── eval/
│   ├── captures/              # 10 captures d'écran de test
│   ├── verite_terrain.yaml    # valeurs notées à la main
│   └── evaluer_extraction.py  # compare extraction ↔ vérité terrain
└── data/                      # journal.db + captures enregistrées (gitignoré)
```

## Lancer les tests

```bash
pip install -r requirements.txt
python -m pytest
```

## Module 2 — Calcul de risque

Entrées : capital, risque max par trade en %, prix d'entrée, stop-loss,
objectif (optionnel). Sorties : sens du trade (déduit de la position du
stop : sous l'entrée → long, au-dessus → short), taille de position,
perte maximale en euros, ratio risque/rendement.

Tout champ invalide (capital nul, stop égal à l'entrée, objectif du
mauvais côté, valeur non numérique…) lève `ErreurValidation` avec un
message en français, jamais un résultat silencieusement faux.
