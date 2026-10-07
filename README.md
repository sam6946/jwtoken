# KEMTA

**La confiance au cœur de votre projet immobilier.** KEMTA est un MVP PropTech camerounais construit comme un monolithe modulaire : une expérience publique claire, un parcours réel de demande de service, une authentification par téléphone/OTP et une API Django qui conserve les projets, profils BTP et candidatures.

## Ce qui fonctionne dans cette première livraison

- Landing page responsive en français, visuels originaux optimisés en WebP et design system KEMTA.
- Demande de service multi-étapes pour construire, reprendre le suivi d’un chantier, entretenir un bien ou décrire un autre besoin. Les demandes sont persistées, référencées `KEMTA-REQ-XXXXXX` et peuvent contenir des pièces jointes JPG/PNG/WebP/PDF validées côté serveur.
- Inscription, connexion par mot de passe ou OTP, vérification téléphone, réinitialisation du mot de passe, rotation du refresh token HttpOnly et RBAC.
- Espace client (propriétaire) : compteur de projets suivis par KEMTA, cartes de projets cliquables, fiche de chantier avec budget, dépenses et **reçus téléchargeables**, demandes rattachées, notifications avec marquage lu, et nouvelle demande pouvant viser un chantier existant.
- Espace KEMTA BTP, profil entreprise, catalogue public vérifié, opportunités paginées et candidatures avec statut.
- Espace d’administration KEMTA avec indicateurs et accès au back-office Django pour traiter les enregistrements.
- Base de données PostgreSQL en Docker, cache/OTP/Celery sur Redis, tâches asynchrones, stockage local en développement et S3 compatible en production.
- Tests API sur les parcours d’authentification, demandes, projets, permissions, profils d’entreprise et candidatures.

Cette livraison est une **base produit fonctionnelle**, pas l’annonce d’un lancement commercial prêt sans configuration. Les passerelles Mobile Money/carte, un fournisseur SMS réel, l’entité légale, les tarifs approuvés et les secrets de production doivent être configurés et testés avec les comptes fournisseurs de KEMTA. Aucun paiement n’est simulé.

## Démarrage local (sans Docker)

Prérequis : Python 3.11+, Node 20+, npm.

Terminal 1 — API (SQLite et cache local si `DATABASE_URL`/`REDIS_URL` ne sont pas définis) :

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_accounts  # facultatif : comptes et données fictifs, DEBUG uniquement
python manage.py runserver 0.0.0.0:8000
```

Terminal 2 — interface :

```bash
cd frontend
npm ci
npm run dev
```

Ouvrir `http://localhost:5173`. Vite relaie `/api`, `/admin`, `/static`, `/media` et `/health` vers Django. Avec `DJANGO_DEBUG=true`, l’API OTP renvoie `debug_code` pour le développement uniquement ; le code est également journalisé côté API. En production, le code n’est jamais inclus dans la réponse HTTP.

La session survit au rechargement de l’onglet : le jeton d’accès est gardé en mémoire et dans le `sessionStorage`, et le cookie de rafraîchissement reste `HttpOnly`. Dans un aperçu embarqué (iframe où les cookies tiers sont bloqués), lancer l’API avec `REFRESH_COOKIE_SAMESITE=None REFRESH_COOKIE_SECURE=true REFRESH_COOKIE_PARTITIONED=true TRUST_PROXY_SSL_HEADER=true EXTRA_ALLOWED_HOSTS=.e2b.app`.

La commande `seed_demo_accounts` crée six comptes de rôles différents et **remplit chaque espace de démonstration** : deux chantiers avec leurs étapes (l’un en cours, l’autre livré), des tâches assignées, des dépenses justifiées par des reçus PDF fictifs générés à la volée, des demandes de service rattachées ou d’origine, une opportunité ouverte, une candidature, un portfolio, des notifications et un journal d’activité. Elle n’agit qu’en mode debug et peut être relancée sans créer de doublons. Sur `/connexion`, le panneau « Aperçu local » permet de préremplir chaque compte ; indicatif `+1`, numéros réservés de démonstration `202-555-0101` à `202-555-0106`, mot de passe commun `KemtaDemo2026!`. Tous les exemples portent la mention DÉMO, le profil BTP n’est ni vérifié ni publié, et l’API signale le contexte fictif (`is_demo`) pour afficher un bandeau d’information dans les espaces.

## Démarrage Docker (PostgreSQL + Redis + Celery)

```bash
cp .env.example .env
# Remplacer les valeurs de développement, au minimum SECRET_KEY et POSTGRES_PASSWORD.
docker compose -f compose.yml -f compose.dev.yml --profile dev up --build
```

- Interface : `http://localhost:5173`
- API : `http://localhost:8000`
- Contrôle de santé : `http://localhost:8000/health/ready/`

Pour afficher les comptes de démonstration dans l’écran de connexion :

```bash
docker compose -f compose.yml -f compose.dev.yml --profile dev exec backend python manage.py seed_demo_accounts
```

Pour créer un compte administrateur local supplémentaire :

```bash
docker compose -f compose.yml -f compose.dev.yml exec backend python manage.py createsuperuser
```

## Tests et contrôles

```bash
cd backend
. .venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test

cd ../frontend
npm run build
```

## API principale

Préfixe versionné : `/api/v1/`.

- `POST /auth/otp/request/`, `POST /auth/otp/verify/`
- `POST /auth/register/`, `POST /auth/login/`, `POST /auth/otp/login/`
- `POST /auth/password-reset/confirm/`, `POST /auth/token/refresh/`, `POST /auth/logout/`, `GET /auth/me/`
- `GET|POST /service-requests/`
- `GET|POST|PATCH /projects/`, `/evidences/`, `/project-tasks/`, `/reports/`
- `GET /companies/`, `GET /companies/{slug}/`, `GET|PUT /companies/me/`, `/portfolio/`
- `GET|POST /opportunities/`, `GET|POST|PATCH /applications/`
- `GET /notifications/`, `POST /notifications/{id}/mark-read/`
- `GET /dashboard/` — réponse agrégée par rôle
- `/health/` et `/health/ready/`

Les listes sont paginées. Le détail des serializers, rôles et statuts est documenté dans [`docs/api.md`](docs/api.md).

## Configuration de production

Consulter [`docs/deployment.md`](docs/deployment.md) et [`docs/security.md`](docs/security.md). Le profil Compose de production utilise Nginx/TLS : fournissez un certificat valide dans `certs/fullchain.pem` et `certs/privkey.pem`, définissez un domaine réel, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, des secrets forts, un stockage objet privé et un fournisseur SMS compatible avec l’adaptateur `http_json`.

Les paiements ont leurs modèles, prix administrables, références idempotentes et contrat d’adaptateur ; ils restent désactivés jusqu’à l’intégration et la validation d’un fournisseur réel. Les mentions légales et conditions d’utilisation contiennent des points à compléter/faire valider localement avant commercialisation.
