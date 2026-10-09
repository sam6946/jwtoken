# Console Administrateur KEMTA

La console est accessible par `/administration` aux rôles `ADMIN` et `SUPER_ADMIN`. Cette barrière visuelle est doublée par les permissions DRF : aucune donnée ni action administrative n'est autorisée par le frontend seul.

## API

Toutes les routes sont sous `/api/v1/admin/` et exigent un compte administration KEMTA :

- `dashboard/?period=1|7|30|90` : indicateurs, série temporelle et alertes agrégées côté serveur ;
- `users/` et `users/<id>/status/` : liste paginée et suspension/réactivation explicite ; un Admin ne peut pas modifier un autre compte administratif ni son propre compte ;
- collections en lecture seule : `companies/`, `projects/`, `requests/`, `missions/`, `reports/`, `incidents/`, `payments/`, `subscriptions/`, `plans/`, `audit/` ;
- `search/?q=` : recherche globale limitée aux utilisateurs, projets, entreprises et missions autorisés ;
- `export/users|projects|missions/` : export CSV plafonné à 5 000 lignes et journalisé ;
- `notifications/send/` : crée uniquement une notification in-app ; elle ne simule aucun SMS, e-mail ou WhatsApp. Un en-tête `Idempotency-Key` est requis pour empêcher un doublon à la reprise de requête ;
- `support-tickets/` : tickets et messages internes de support ;
- `settings/` : paramètres de plateforme **non secrets**, exclusivement pour `SUPER_ADMIN`.

Les listes appliquent la pagination standard de l’API. Les paramètres de recherche et filtrage restent traités côté serveur ; les exportations disponibles sont volontairement limitées.

## Sécurité et journalisation

Les actions sensibles réalisées par cette app utilisent `write_audit_event` : suspension/réactivation, envoi d'une notification, création/mise à jour de ticket, export et modification des paramètres. Les événements ne doivent jamais contenir de mot de passe, OTP, jeton, secret de fournisseur ou donnée de carte.

Les paiements, plans et abonnements sont affichés à titre de supervision en lecture seule. Aucun endpoint de remboursement, de débit, de facture ou de changement de fournisseur n'est introduit : il n'existe pas de fournisseur de paiement configuré dans l'application.

## Déploiement

Appliquer la migration additive avant de déployer le frontend :

```bash
cd backend
python manage.py migrate
```

Contrôles effectués pour cette évolution :

```bash
cd backend && python manage.py test administration
cd frontend && npm run build
```
