# Contrats API KEMTA (`/api/v1/`)

Les erreurs de validation sont des réponses JSON avec un code HTTP 4xx. Les routes privées attendent `Authorization: Bearer <access>`. Le refresh est géré par le cookie `kemta_refresh` et ne doit pas être lu par JavaScript. Les numéros sont normalisés au format E.164 ; l’interface propose l’indicatif camerounais par défaut et plusieurs indicatifs courants pour les propriétaires de la diaspora.

## Authentification téléphone + OTP

### Demander un code

`POST /auth/otp/request/`

```json
{ "phone": "+237677123456", "purpose": "REGISTER" }
```

`purpose` : `REGISTER`, `LOGIN`, `PASSWORD_RESET`. Le code expire en cinq minutes par défaut et comporte au maximum cinq essais. Réponse de production :

```json
{ "detail": "Si le numéro peut recevoir un code, celui-ci vient d’être envoyé.", "expires_in": 300 }
```

`debug_code` existe uniquement en environnement `DJANGO_DEBUG=true`.

### Vérifier un code

`POST /auth/otp/verify/`

```json
{ "phone": "+237677123456", "code": "123456", "purpose": "REGISTER" }
```

Retourne `verification_token` et le téléphone normalisé. Le token est signé, court et à usage unique.

### Inscription

`POST /auth/register/`

```json
{
  "phone": "+237677123456",
  "verification_token": "…",
  "first_name": "Awa",
  "last_name": "Fouda",
  "email": null,
  "password": "un mot de passe robuste",
  "role": "CUSTOMER",
  "terms_accepted": true
}
```

Les seuls rôles auto-inscriptibles sont `CUSTOMER` et `BTP_COMPANY`. Succès : `{ "access": "…", "user": { … } }` et cookie HttpOnly `kemta_refresh`.

### Connexion et réinitialisation

- `POST /auth/login/`: `{ "phone": "+237…", "password": "…" }`
- `POST /auth/otp/login/`: `{ "verification_token": "…" }` après OTP `LOGIN`
- `POST /auth/password-reset/confirm/`: `{ "verification_token": "…", "password": "…" }` après OTP `PASSWORD_RESET`
- `POST /auth/token/refresh/`: cookie refresh requis ; retourne un access token et renouvelle le cookie.
- `POST /auth/logout/`: blacklist le refresh courant et supprime le cookie.
- `GET /auth/me/`: profil courant.

Les demandes de code `LOGIN`/`PASSWORD_RESET` restent génériques pour réduire l’énumération de comptes.

## Demandes de service

`POST /service-requests/` accepte JSON ou `multipart/form-data`. Le champ `metadata` est un objet JSON (en multipart : chaîne JSON) ; les pièces jointes multiples utilisent la clé `attachments`.

```json
{
  "service_type": "BUILD",
  "first_name": "Awa",
  "last_name": "Fouda",
  "phone": "+237677123456",
  "email": "awa@example.com",
  "city": "Douala",
  "project_type": "Villa",
  "description": "Maison familiale…",
  "metadata": { "budget_fcfa": 25000000, "desired_date": "2027-02" }
}
```

`service_type`: `BUILD`, `TAKEOVER`, `MAINTENANCE`, `OTHER`. Max. 5 pièces jointes, 8 Mo par fichier, 32 Mo cumulé ; seules images JPG/PNG/WebP valides et PDF avec signature `%PDF-` sont acceptés. Si l’utilisateur est connecté, la demande est associée à son compte ; sinon elle est conservée comme demande non rattachée.

## Projets et suivi

- `GET /projects/` : projets visibles par l’utilisateur.
- `POST /projects/` : rôle de gestionnaire, owner obligatoire ; un jeu de phases initiales est créé.
- `GET /projects/{id}/` : fiche complète du projet — phases ordonnées, `budget`, `expenses` et `service_requests`.
- `GET /projects/{id}/evidences/` : preuves du projet.
- `/evidences/` : ajouter une image terrain ou réviser son statut selon le grant.
- `/project-tasks/` : tâches de projet ; `/reports/` : rapports.

Les clients ne voient que leurs projets. Les budgets ne sont pas sérialisés pour un rôle sans grant `VIEW_FINANCE`.

### Dépenses et justificatifs

- `GET /project-expenses/?project={id}` : dépenses d’un chantier (filtre `status` également accepté).
- `POST /project-expenses/` : grant `MANAGE_FINANCE`. Champs : `project`, `label`, `category`, `amount`, `spent_at`, `status`, `reference`, `notes` et `receipt` (PDF/JPG/PNG/WebP, 8 Mo maximum).
- `GET /project-expenses/{id}/receipt/` : télécharge le justificatif en pièce jointe. L’accès est revérifié à chaque appel (propriétaire, gestionnaire ou administration) ; aucun reçu n’est servi depuis `/media/`.

`category` : `MATERIALS`, `LABOUR`, `EQUIPMENT`, `TRANSPORT`, `ADMIN`, `OTHER`. `status` : `DECLARED`, `VALIDATED`, `REJECTED`.

`GET /projects/{id}/` renvoie pour le propriétaire :

```json
{
  "budget": {
    "total": "25000000.00", "spent": "10500000.00", "remaining": "14500000.00",
    "expenses_total": "10500000.00", "justified_total": "8300000.00",
    "expense_count": 3, "receipt_count": 3, "currency": "XAF"
  },
  "expenses": [
    { "id": 1, "label": "Acompte fondations", "amount": "4500000.00", "status": "VALIDATED",
      "status_label": "Justifiée", "has_receipt": true, "receipt_url": "/project-expenses/1/receipt/" }
  ],
  "service_requests": [
    { "id": 2, "request_code": "KEMTA-REQ-DEMO-02", "status_label": "En étude", "is_origin": false }
  ]
}
```

`receipt_url` est un chemin relatif à la racine de l’API : le client l’appelle avec son propre préfixe et son en-tête d’authentification. `service_requests` réunit les demandes rattachées au chantier et la demande d’origine (`is_origin: true`), sans doublon.

### Rattacher une demande à un chantier existant

`POST /service-requests/` accepte `related_project` (identifiant). La demande n’est acceptée que si le projet appartient au demandeur ; dans le cas contraire l’API répond 400 sur `related_project`. Le propriétaire retrouve alors la demande dans la fiche de son chantier et dans `GET /dashboard/` (`related_project_name`).

## Entreprises BTP et catalogue

- `GET /companies/?page_size=12&search=Douala` : profils publiés uniquement, recherche nom/ville/présentation, pagination.
- `GET /companies/{slug}/` : profil public et réalisations publiées.
- `GET /companies/me/` : profil propre, 404 s’il n’existe pas encore.
- `PUT /companies/me/` : crée ou remplace le profil ; `PATCH /companies/me/` enregistre une mise à jour partielle (notamment « continuer plus tard »). Les champs `verified` et `is_published` sont uniquement administrables.
- `/portfolio/` : gestion des réalisations par l’entreprise liée.

Un profil n’est public qu’après publication par l’équipe KEMTA. Le fait de compléter le formulaire ne confère pas automatiquement un badge vérifié.

### Vérification d’entreprise

L’inscription `BTP_COMPANY` accepte le champ optionnel `company_name` et crée un profil brouillon. Elle reste protégée par le même OTP d’inscription que les autres comptes.

- `GET|POST /companies/me/documents/` : liste ou ajoute/remplace une pièce privée. Le `POST` est un `multipart/form-data` avec `document_type` et `file` ; les formats PDF/JPG/PNG/WebP sont limités à 8 Mo.
- `GET /companies/me/documents/{id}/file/` : sert une pièce après contrôle de propriété ; l’entreprise propriétaire, un administrateur KEMTA ou un membre staff autorisé y accède. Le catalogue public n’expose jamais ces fichiers.
- `GET /companies/me/verification/` : renvoie le statut, le niveau, la checklist, les pièces, les champs manquants et les dates de décision.
- `POST /companies/me/verification/submit/` : soumet le dossier lorsque le profil et les trois pièces obligatoires sont complets (`RCCM`, `NIU`, pièce d’identité du représentant légal).
- `GET /companies/verification/queue/?limit=20` : file des dossiers `PENDING` ou `UNDER_REVIEW`, réservée à KEMTA.
- `POST /companies/{id}/verification/` : décision KEMTA avec `action` parmi `start_review`, `approve`, `reject`, `request_correction`, `suspend`. Un motif d’au moins cinq caractères est obligatoire pour les décisions négatives ; `document_type` cible une pièce lors de `request_correction`.

Les statuts de dossier sont `DRAFT`, `PENDING`, `UNDER_REVIEW`, `VERIFIED`, `REJECTED` et `SUSPENDED`. Les niveaux sont `ACCOUNT`, `PROFILE`, `BUSINESS_VERIFIED` et `ADVANCED`. Les actions génèrent un audit et une notification via les services existants.

## Opportunités et candidatures

- `GET /opportunities/?status=OPEN&city=Douala` : opportunités ouvertes non expirées ; la pagination est activée.
- `POST /opportunities/` : permission `CREATE_OPPORTUNITY`.
- `GET|POST /applications/` : une candidature par entreprise et opportunité ; entreprise BTP vérifiée requise.
- `PATCH /applications/{id}/` : mise à jour du statut par l’équipe KEMTA.
- `POST /applications/{id}/withdraw/` : retrait par l’entreprise propriétaire si la candidature est encore retirable.

Statuts : `SUBMITTED`, `IN_REVIEW`, `SHORTLISTED`, `ACCEPTED`, `REJECTED`, `WITHDRAWN`.

## Dashboard et notifications

`GET /dashboard/` retourne le profil, le rôle, les permissions, les indicateurs calculés pour ce rôle, puis les données utiles à l’écran d’accueil : `projects`, `tasks` (tâches de chantier avec projet, étape et assignation), `evidences` (preuves terrain à vérifier ou transmises), `service_requests` (avec `owner_name` pour l’administration), `company` (profil de l’entreprise connectée), `companies` (file de vérification pour l’administration), `opportunities`, `applications` (candidatures de l’entreprise) et `recent_activity`. Le champ `is_demo` signale un compte de démonstration (`*@kemta.invalid`) afin que l’interface affiche un bandeau explicite. Les grandes listes restent sur leurs endpoints paginés.

Les tâches de chantier sont exposées par `GET /project-tasks/` (projet, étape, assigné, statut, échéance). Un agent terrain peut faire évoluer le statut d’une tâche qui lui est assignée avec `PATCH /project-tasks/{id}/` ; toute autre modification reste réservée aux rôles disposant de `MANAGE_PROJECT`.

- `GET /notifications/?unread=1&type=PROJECT` : filtre sur les notifications non lues et par type.
- `GET /notifications/summary/` : compteurs `unread` et `total` pour la pastille du menu.
- `GET /notifications/`
- `POST /notifications/{id}/mark-read/`
- `POST /notifications/mark-all-read/`

## Santé

- `/health/` : processus API vivant.
- `/health/ready/` : teste PostgreSQL et le cache configuré ; retourne `503` si une dépendance est indisponible.

## Paiements

Les modèles `SubscriptionPlan`, `Subscription`, `Payment` et `PaymentTransaction` sont configurables via le back-office. `payments.providers.PaymentProvider` définit le contrat d’intégration et `create_payment_intent` protège la clé d’idempotence. L’appel échoue volontairement tant qu’un adaptateur MTN MoMo, Orange Money ou carte réellement configuré n’est pas installé. Aucun webhook ni faux statut de paiement n’est exposé.

## Opérations terrain : missions, rapports et problèmes

Les tableaux Chef de Projet et Agent Terrain sont alimentés par `GET /dashboard/field-operations/`. Cette réponse est agrégée, plafonnée et réservée aux deux rôles ; les historiques passent par les ressources paginées ci-dessous.

- `GET|POST|PATCH /project-assignments/` : affectations d’agents par le Chef du projet.
- `GET|POST|PATCH /field-missions/` : missions ; un agent ne voit que celles qui lui sont affectées.
- `POST /field-missions/{id}/accept/` et `POST /field-missions/{id}/start/` : transitions Agent. `start` accepte éventuellement `latitude` et `longitude` si la mission demande une confirmation ponctuelle de lieu.
- `GET|POST|PATCH /field-reports/`, puis `POST /field-reports/{id}/submit/` : un rapport par mission, créé et modifié par l’agent auteur.
- `POST /field-reports/{id}/start-review/`, `/approve/`, `/request-revision/` : revue du Chef du projet. Une correction exige `{"reason": "…"}` ; l’auteur ne peut jamais valider son rapport.
- `GET|POST|PATCH /project-issues/` : anomalies déclarées depuis une mission propre, puis traitées par le Chef.

Une mission suit `PLANNED → ACCEPTED → IN_PROGRESS → SUBMITTED → UNDER_REVIEW → APPROVED`, avec la boucle `REVISION_REQUIRED → IN_PROGRESS → SUBMITTED`. `Evidence` accepte `evidence_type: PHOTO|VIDEO`, une liaison `mission`/`issue` et les coordonnées facultatives. Une création hors connexion doit envoyer `client_reference` ou l’en-tête `Idempotency-Key`; les créations répétées avec cette référence retournent la ressource existante.

La description complète de sécurité, stockage média et reprise IndexedDB est dans [`field-work.md`](field-work.md).
