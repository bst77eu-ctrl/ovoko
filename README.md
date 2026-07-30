# Assistant de pré-trade avec analyse de capture d'écran

> **Outil d'aide à la discipline. Aucune recommandation d'investissement.**

## Contrainte absolue

Cet outil ne produit **jamais** :
- de signal d'achat ou de vente,
- de prédiction de direction de prix,
- de score de confiance sur un résultat futur.

Cette contrainte est appliquée à trois niveaux :
1. **Prompt système** (`app/extraction.py`) : le modèle a pour instruction
   de répondre « non déterminable depuis une image » à toute demande de
   prévision, et de mettre `null` sur tout champ non lisible.
2. **Normalisation structurelle** : la sortie du modèle est ramenée à un
   schéma fermé — toute clé étrangère (recommandation, probabilité,
   objectif prévu…) est supprimée, toute tendance hors énumération devient
   `indeterminee`. Testé dans `tests/test_parsing.py`.
3. **Frontend** : bandeau permanent, `tendance_visuelle` étiquetée
   « descriptive », `fiabilite_lecture` étiquetée comme lisibilité d'image.

## Installation et lancement

```bash
pip install -r requirements.txt
cp .env.example .env        # puis renseigner ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

Ouvrir <http://127.0.0.1:8000>. Tout est local : SQLite (`data/journal.db`),
captures (`data/captures/`), aucun service tiers autre que l'API Claude.

## Modules

| Module | Fichier | Rôle |
|---|---|---|
| 1 — Extraction | `app/extraction.py` | Lecture d'image via Claude (`claude-sonnet-4-6`), JSON strict, normalisation défensive |
| 2 — Risque | `app/risque.py` | Taille de position, perte max, ratio R/R — **pur calcul, zéro IA** |
| 3 — Checklist | `app/checklist.py` + `checklist.yaml` | Questions éditables, réponse explicite oui/non exigée partout |
| 4 — Journal | `app/journal.py`, `app/stats.py` | SQLite, résultat après clôture, stats et corrélation checklist/résultats |

### Module 2 — calcul de risque

Entrées : capital, risque max par trade en %, prix d'entrée, stop-loss,
objectif (optionnel). Le sens du trade est déduit de la position du stop :
sous l'entrée → long, au-dessus → short. Toute entrée invalide (capital
nul, stop égal à l'entrée, objectif du mauvais côté, NaN…) lève
`ErreurValidation` en français. Le calcul est **toujours refait côté
serveur** à l'enregistrement — le frontend n'est jamais une source de
vérité.

### Module 3 — décision d'interprétation à valider

La spécification demandait un bouton désactivé « tant que tout n'est pas
coché ». Implémentation retenue : chaque question exige une réponse
**explicite** oui/non (jamais pré-remplie), et l'enregistrement exige une
réponse partout — mais un « non » est accepté. Raison : si tous les trades
enregistrés avaient 100 % de « oui », la corrélation entre cases non
respectées et pertes (la « vraie valeur de l'outil », module 4) serait
mathématiquement impossible à calculer. Si vous préférez le blocage strict
sur « tout oui », c'est un changement d'une ligne dans
`app/checklist.py` — dites-le.

### Module 4 — journal et statistiques

Résultat saisi en euros après clôture ; le résultat en R (multiples du
risque initial) est dérivé automatiquement (`resultat_eur / perte_max`).
La page statistiques affiche : nombre de trades, winrate, gain/perte
moyens, espérance, et pour chaque question de la checklist la comparaison
winrate/résultat moyen entre les trades « oui » et les trades « non ».

## Tests

```bash
python -m pytest
```

- `tests/test_risque.py` — cas limites du calcul de risque (28 tests)
- `tests/test_parsing.py` — réponses malformées du modèle (fixtures dans
  `tests/fixtures/reponses_malformees/`), y compris l'injection de clés
  interdites (« recommandation : acheter ») qui doivent être supprimées
- `tests/test_checklist.py` — validation du YAML et des réponses
- `tests/test_journal_stats.py` — persistance SQLite et corrélations
- `tests/test_api.py` — endpoints FastAPI, dont le refus d'un trade à
  checklist incomplète (l'appel réseau au modèle est simulé)

## Mesurer la fiabilité de la lecture

1. Déposez 10 captures d'écran dans `eval/captures/`.
2. Notez à la main les valeurs réellement lisibles dans
   `eval/verite_terrain.yaml` (un champ illisible pour vous vaut `null` —
   le modèle est attendu sur `null` aussi).
3. `python eval/evaluer_extraction.py`

Le script distingue trois issues par champ : **correct**, **manque**
(lisible mais le modèle a répondu `null` — prudence excessive, sans
danger) et **erreur** (valeur fausse qui a l'air vraie — le cas à
surveiller).

## Arborescence

```
ovoko/
├── checklist.yaml             # vos questions de pré-trade, éditables
├── .env.example               # ANTHROPIC_API_KEY, modèle, chemins
├── app/
│   ├── main.py                # FastAPI : routes + service du frontend
│   ├── risque.py              # Module 2 (déterministe, sans IA)
│   ├── extraction.py          # Module 1 (vision + parsing strict)
│   ├── checklist.py           # Module 3
│   ├── journal.py             # Module 4 (SQLite)
│   └── stats.py               # winrate + corrélation checklist/résultats
├── static/index.html          # frontend une page (collage Ctrl+V)
├── zip-studio.html            # outil séparé : ouvrir/renommer/recréer un .zip
├── tests/                     # pytest (aucun appel réseau)
├── eval/                      # captures + vérité terrain + script d'évaluation
└── data/                      # journal.db + captures (créé au lancement, gitignoré)
```

## Outil annexe : `zip-studio.html`

Fichier HTML autonome, sans lien avec le reste du projet et sans serveur :
**double-cliquez-le** pour l'ouvrir dans un navigateur.

- déposez un `.zip` (ou des fichiers, pour partir de rien) ;
- renommez l'archive à la main ou avec les boutons (nettoyage du nom, date) ;
- renommez chaque fichier interne, en série (`photo-###`) ou un par un ;
- regardez les images contenues (galerie + visionneuse plein écran,
  flèches ← → et Échap) ;
- créez le nouveau `.zip`, avec relecture de contrôle de l'archive produite.

Lecture et écriture du format ZIP en JavaScript pur (`DecompressionStream` /
`CompressionStream`) : aucune bibliothèque, aucun accès réseau, aucun fichier
ne quitte la machine. Limites connues : pas de ZIP64 en écriture (4 Go max),
et les entrées protégées par mot de passe sont signalées mais pas déchiffrées.
