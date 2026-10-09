# Sécurité — contrôles et limites

## Contrôles présents

- OTP 6 chiffres aléatoire, hashé avec le hasher Django et conservé en Redis à TTL court ; remplacement d’un ancien code, usage unique du challenge, limite d’essais, limites par numéro et throttling DRF.
- Téléphone comme identifiant unique ; email nullable ; validation de rôle refusant les rôles admin à l’inscription.
- Mots de passe soumis aux validateurs Django et stockés via les hashers Django ; réinitialisation OTP invalide les refresh tokens antérieurs.
- Access JWT 10 minutes ; refresh token rotatif, blacklist après rotation, cookie HttpOnly/SameSite et Secure en production ; access token conservé en mémoire et copié dans le `sessionStorage` de l’onglet pour survivre à un rechargement, jamais dans un stockage persistant partagé.
- Le cookie de session reste HttpOnly : il n’est jamais lisible par JavaScript. Dans un aperçu embarqué (iframe) où les navigateurs bloquent les cookies tiers, `REFRESH_COOKIE_SAMESITE=None`, `REFRESH_COOKIE_SECURE=true` et `REFRESH_COOKIE_PARTITIONED=true` activent un cookie partitionné (CHIPS). Hors de ce cas, conserver `SameSite=Lax`.
- `ALLOW_TOKEN_AUTH_HEADER_FALLBACK` (désactivé par défaut, activé seulement quand `DJANGO_DEBUG=true`) accepte le jeton d’accès dans `X-Kemta-Auth` lorsque l’en-tête `Authorization` a été retiré en transit par un proxy d’aperçu. Le jeton est validé exactement de la même façon (signature, expiration, type) ; ce n’est qu’un second transport.
- `REFRESH_TOKEN_IN_BODY` (désactivé par défaut, activé seulement quand `DJANGO_DEBUG=true`) renvoie aussi le refresh token dans la réponse de connexion, afin qu’un aperçu dont les cookies tiers sont bloqués puisse renouveler sa session par le corps de la requête. Ce mode réduit la protection contre le XSS : ne jamais l’activer en production.
- Un renouvellement qui échoue ne peut jamais remplacer une session plus récente : la session ouverte après le démarrage de la requête est conservée, et l’application revient explicitement à l’écran de connexion lorsqu’elle est réellement expirée (aucune rafale de 401).
- Permissions backend, grants RBAC et filtrage par propriétaire ; champs budget écartés de la réponse aux rôles sans `VIEW_FINANCE`.
- Validation serveur du contenu uploadé, extension/MIME, signature PDF, taille/quantité et vérification Pillow des images ; objets distincts de la base métier.
- Limites de débit, `X-Request-ID`, audit de plusieurs actions métier, CORS sans wildcard, health check PostgreSQL/cache.
- En-têtes de sécurité et TLS Nginx en configuration production.

## Vérifications obligatoires avant lancement

- Remplacer tous les secrets de `.env.example`. `SECRET_KEY=change-me-before-deployment` et les mots de passe d’exemple ne sont jamais acceptables en production.
- Définir `DJANGO_DEBUG=false`, `ALLOWED_HOSTS`, CORS/CSRF, TLS, HSTS et un bucket média privé.
- Installer un fournisseur SMS réel et tester distribution, délais, erreurs, renvoi et coûts. `debug_code` n’est disponible qu’en mode debug ; `SMS_PROVIDER=console` n’envoie aucun SMS réel.
- Sélectionner puis intégrer un prestataire de paiement. Les clés API, les signatures de webhook, la vérification des callbacks, les états idempotents, remboursements et rapprochements ne sont pas encore raccordés à un fournisseur.
- Ajouter analyse antivirus/quarantaine pour les documents, politique de rétention/suppression et journalisation d’accès objet avant d’héberger de vrais fichiers clients.
- Configurer monitoring/alertes, gestion des incidents, sauvegardes chiffrées et restauration éprouvée.
- Faire relire les contrats, consentements, mentions, transferts éventuels de données et durées de rétention par un conseil compétent au Cameroun.
- Faire un audit indépendant de sécurité, de charge et de configuration d’infrastructure avant d’ouvrir les comptes clients.

## Modèle de menace pratique

Ne pas envoyer OTP, refresh token, mot de passe, URL S3 signée ni pièce jointe dans les logs. Limiter l’accès réseau PostgreSQL/Redis au réseau interne des conteneurs. Les comptes `ADMIN` doivent être attribués par l’équipe KEMTA, utiliser des identifiants robustes et être audités régulièrement. La connexion OTP est disponible ; une politique de MFA obligatoire pour les administrateurs reste à activer avant un lancement à risque élevé.
