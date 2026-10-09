# Déploiement et exploitation

## Préparation des secrets

1. Créer `.env` depuis `.env.example` et ne jamais le versionner.
2. Générer `SECRET_KEY` Django et `JWT_SECRET` séparément, avec des valeurs aléatoires fortes. Remplacer aussi `POSTGRES_PASSWORD` par une valeur URL-safe (par exemple hexadécimale : `openssl rand -hex 32`), car Compose construit `DATABASE_URL` à partir de ce secret.
3. Définir `DJANGO_ENV=production`, `DJANGO_DEBUG=false`, `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` avec les domaines réels. Activer `SECURE_SSL_REDIRECT=true`, `SECURE_HSTS_SECONDS` et `REFRESH_COOKIE_SECURE=true`. Derrière un proxy terminant TLS (Nginx, aperçu sandbox), activer `TRUST_PROXY_SSL_HEADER=true` et compléter `EXTRA_ALLOWED_HOSTS` avec les domaines servis (un préfixe `.` autorise les sous-domaines).
   Le cookie de session reste `SameSite=Lax` en production. Pour un aperçu embarqué en iframe où les cookies tiers sont bloqués, utiliser `REFRESH_COOKIE_SAMESITE=None` + `REFRESH_COOKIE_PARTITIONED=true` (cookie partitionné, HTTPS obligatoire).
4. Configurer un bucket S3/R2/MinIO privé et des identifiants limités au bucket. Ne pas activer un domaine média public pour les pièces privées.
5. Choisir un prestataire SMS et installer/valider l’adaptateur correspondant. L’adaptateur `http_json` actuel attend un endpoint qui accepte `POST { "to": "+237…", "message": "…" }` avec `Authorization: Bearer …` ; ce contrat n’est pas une certification d’un fournisseur particulier.
6. Créer `certs/fullchain.pem` et `certs/privkey.pem` pour Nginx. Le renouvellement TLS doit être supervisé par le propriétaire de l’infrastructure.
7. Compléter et faire valider les mentions légales, conditions d’utilisation, politique de conservation et coordonnées de contact pour le Cameroun.

## Lancer en production

```bash
docker compose -f compose.yml -f compose.prod.yml --profile prod run --rm backend python manage.py migrate
docker compose -f compose.yml -f compose.prod.yml --profile prod run --rm backend python manage.py createsuperuser
docker compose -f compose.yml -f compose.prod.yml --profile prod up -d --build
```

Nginx écoute sur HTTP/HTTPS et redirige HTTP vers HTTPS. Les certificats sont montés en lecture seule depuis `./certs`. Avant d’ouvrir l’accès : vérifier `https://<domaine>/health/ready/`, le cookie refresh `Secure`, les entêtes de sécurité, les migrations, le fournisseur SMS, les mails, le bucket et les webhooks de paiement retenus.

## Développement conteneurisé

```bash
cp .env.example .env
docker compose -f compose.yml -f compose.dev.yml --profile dev up --build
```

Le backend de développement applique les migrations au démarrage. L’interface Vite est publiée sur le port `VITE_PORT` (5173 par défaut), l’API sur `API_PORT` (8000 par défaut). Le service Redis n’expose pas de port au réseau hôte.

## Opérations courantes

```bash
# Logs
docker compose -f compose.yml -f compose.prod.yml --profile prod logs -f backend celery_worker celery_beat nginx

# Vérification du code / migrations (depuis backend)
python manage.py check
python manage.py makemigrations --check --dry-run

# Collecte statique Nginx/Django (déjà exécutée à la construction de l’image)
python manage.py collectstatic --noinput
```

Planifier des sauvegardes chiffrées et testées de PostgreSQL et du stockage objet, conserver des journaux sans OTP/token/mot de passe, suivre la profondeur Redis/Celery, les erreurs SMS/paiement et le temps de réponse API. Les sauvegardes et plans de restauration doivent être validés avant toute donnée client réelle.

## Mise à niveau

- Construire et tester une nouvelle image sans déployer directement en base.
- Sauvegarder la base et le stockage objet.
- Exécuter `migrate` comme opération unique avant de relancer les nouveaux workers.
- Surveiller `/health/ready/`, l’état Celery et les erreurs de validation pendant le déploiement.
- Garder une procédure de retour arrière des images ; une migration destructive exige une étape de compatibilité préalable.
