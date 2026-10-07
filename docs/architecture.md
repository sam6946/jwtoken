# Architecture KEMTA

## Principes

- Monolithe modulaire Django : aucun microservice.
- Contrats HTTP JSON versionnés sous `/api/v1/`.
- Frontend React/TypeScript en SPA, Vite en développement et Nginx/static en production.
- PostgreSQL pour les données métier persistantes ; Redis pour cache, limites de débit, OTP temporaires et broker Celery.
- Images et documents stockés via `FileField` dans un stockage objet S3 compatible si configuré ; PostgreSQL ne contient que le chemin et les métadonnées.
- Une seule requête `GET /api/v1/dashboard/` rassemble profil, permissions, statistiques et les premiers éléments utiles au rôle actif.

## Modules backend

| Module | Responsabilité |
| --- | --- |
| `accounts` | utilisateur téléphone, rôles/grants, OTP Redis, JWT/cookie refresh |
| `service_requests` | demandes de service, référence, validation et pièces jointes |
| `projects` | projets, phases, tâches, preuves, rapports et dérivés d’images Celery |
| `companies` | profils BTP, réalisations, vérification et catalogue public caché |
| `opportunities` | appels ouverts, candidatures et transitions de statut |
| `notifications` | notifications in-app et tâches SMS/email |
| `payments` | plans, abonnements, paiements, idempotence et contrat fournisseur |
| `dashboard` | vue agrégée adaptée au rôle et aux accès |
| `common` | pagination, health checks, audit log, request ID |

## Flux d’authentification

1. Normaliser le numéro au format international ; l’interface client saisit un numéro camerounais à 9 chiffres avec indicatif `+237`.
2. Générer un OTP aléatoire de six chiffres. Stocker dans Redis uniquement le hash, l’objet, le compteur d’essais et l’expiration ; un nouvel OTP remplace l’ancien.
3. Limiter les demandes par IP (DRF) et par numéro/objectif (cache). Après vérification, émettre un jeton de vérification signé, à durée courte et à usage unique, consommé lors de l’inscription ou de la réinitialisation.
4. Émettre un access token de courte durée en réponse et placer le refresh token rotatif dans un cookie `HttpOnly`, `SameSite=Lax`, `Secure` en production. L’interface garde l’access token en mémoire, pas dans `localStorage`.
5. Lors d’une réinitialisation, invalider les refresh tokens existants.

## Accès et rôles

Les rôles sont `CUSTOMER`, `BTP_COMPANY`, `FIELD_AGENT`, `PROJECT_MANAGER`, `ADMIN` et `SUPER_ADMIN`. Les grants sont persistés dans `RoleGrant` et vérifiés côté API (`HasKemtaPermission`), en complément des contrôles de propriété sur projets, demandes, entreprises et candidatures. Les grants initiaux sont insérés après migration ; les changements de grants sont mis en cache au plus cinq minutes.

Les identifiants client ne permettent pas de choisir `ADMIN` ou `SUPER_ADMIN` à l’inscription. Le super-administrateur doit être créé par une opération d’administration contrôlée.

## Travaux asynchrones

Celery traite les SMS, emails et dérivés d’images terrain. Redis TTL expire automatiquement OTP et challenges ; une tâche Beat retire par sécurité les clés d’authentification persistantes accidentelles. Les tâches HTTP restent hors des chemins critiques de production.

## Stockage média

Quand `OBJECT_STORAGE_ENDPOINT` et `OBJECT_STORAGE_BUCKET` sont définis, Django utilise `django-storages` et un stockage S3 compatible avec URL signée. Les originaux, miniatures WebP et tailles medium/large d’une preuve sont des objets séparés. En développement, `MEDIA_ROOT` local est activé et les médias passent par le proxy Vite vers Django. Nginx ne sert pas `MEDIA_URL` ; le lancement commercial doit employer un bucket privé, des URL signées pour les objets privés et une politique de conservation.

## Performance

- pagination globale (20 par défaut, 100 maximum) ; indexes sur rôle/statut, date, propriétaire et relation de liste ;
- `select_related`/`prefetch_related` sur les lectures métier concernées ;
- React Query partage les requêtes en vol, conserve les résultats 60 secondes par défaut et évite les refetch au focus ;
- images marketing WebP responsive ; assets Vite hashés servis avec cache immutable ;
- cache Redis de cinq minutes pour le catalogue public ; données privées non mises en cache globalement.
