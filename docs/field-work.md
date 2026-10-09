# Opérations terrain KEMTA

Les dashboards **Chef de Projet** et **Agent Terrain** partagent le même domaine `projects`, sans modifier les parcours client, BTP ou finance existants.

## Workflow

Une `FieldMission` suit exclusivement les transitions suivantes :

```text
PLANNED → ACCEPTED → IN_PROGRESS → SUBMITTED → UNDER_REVIEW → APPROVED
                         ↑                 │
                         └─ REVISION_REQUIRED ─┘
```

- l’agent affecté accepte, démarre, renseigne la checklist, ajoute des preuves et soumet son rapport ;
- le Chef de Projet prend le rapport en revue, le valide ou exige une correction motivée ;
- un agent ne peut jamais valider son propre rapport, modifier une affectation, ni modifier un budget ou projet ;
- les transitions, l’audit et les notifications sont centralisés dans `projects.field_workflow` et non dans React.

`ProjectAssignment` complète `Project.field_agents`, qui demeure conservé pour les écrans et données historiques. La migration `projects.0003_field_workflow` crée une affectation active pour chaque agent terrain déjà lié à un projet.

## Endpoints

Tous sont préfixés par `/api/v1/` et restent soumis à l’authentification JWT/cookie existante.

| Endpoint | Rôle et usage |
| --- | --- |
| `GET /dashboard/field-operations/` | dashboard agrégé, limité et préchargé pour Chef/Agent |
| `GET|POST|PATCH /project-assignments/` | affectations, Chef du projet uniquement |
| `GET|POST|PATCH /field-missions/` | lecture restreinte ; planification/replanification par Chef |
| `POST /field-missions/{id}/accept/` | agent affecté |
| `POST /field-missions/{id}/start/` | agent affecté ; reçoit `latitude`, `longitude` uniquement si la mission demande une confirmation de lieu |
| `GET|POST|PATCH /field-reports/` | brouillon/lecture selon propriété ; une mission possède un seul rapport |
| `POST /field-reports/{id}/submit/` | agent auteur |
| `POST /field-reports/{id}/start-review/`, `/approve/`, `/request-revision/` | Chef du projet, distinct de l’auteur ; motif requis pour correction |
| `GET|POST|PATCH /project-issues/` | signalement depuis sa propre mission, traitement par Chef |
| `POST /evidences/` | preuve photo ou vidéo ; l’agent doit joindre une de ses missions |

Les endpoints de liste sont paginés. Les écrans d’accueil utilisent le dashboard agrégé, plafonné, et les lectures lourdes utilisent `select_related`/indexes dédiés.

## Médias, confidentialité et connexion faible

Les photos et vidéos restent dans les `FileField`/stockage objet ; PostgreSQL ne reçoit que leur chemin et métadonnées. Les photos continuent de générer les dérivés WebP Celery existants. Les vidéos sont limitées à 30 Mo et aux formats MP4, MOV ou WebM.

L’interface terrain utilise une outbox IndexedDB. Checklist, rapport, signalement et fichiers sont conservés lorsque le navigateur est hors ligne, puis repris dans l’ordre au retour du réseau. Chaque création porte `client_reference` et l’API accepte `Idempotency-Key` : une reprise ne crée pas une seconde preuve, un second problème ou rapport.

Aucun GPS permanent n’est implémenté. La géolocalisation n’est demandée qu’au clic sur **Démarrer la visite** et seulement si `requires_geo_confirmation` est activé par le Chef de Projet.
