# Périmètre de cette première tranche

Cette tranche met en place une première version utilisable de la vision KEMTA sans simuler les systèmes qui exigent des contrats fournisseurs ou des opérations métier réelles.

## Parcours déjà câblés

- demande client → validation → persistance → référence de suivi ;
- OTP → inscription, connexion OTP, connexion par mot de passe ou reset → session courte avec refresh cookie ;
- rôle → endpoint dashboard correspondant ;
- gestionnaire → création de projet → phases initiales et propriétaires ;
- agent terrain autorisé → preuve image → dérivés WebP via Celery ;
- entreprise → édition de profil → contrôle/publication par administrateur → catalogue public ;
- profil BTP vérifié → candidature sur une opportunité ouverte → suivi du statut côté entreprise/KEMTA ;
- propriétaire → compteur de projets suivis → fiche de chantier (budget, dépenses, reçus, demandes) → nouvelle demande rattachée à un chantier ;
- équipe KEMTA → dépense de chantier avec justificatif → téléchargement contrôlé par le propriétaire.

## À compléter avant lancement commercial

- adaptation de l’API SMS à un fournisseur contractuel choisi et test des livraisons dans les réseaux camerounais ;
- intégration Mobile Money (MTN MoMo, Orange Money) et éventuellement carte, webhooks signés, remboursement, facture et rapprochement ;
- édition complète des profils/réalisations, messagerie client-entreprise, rapports PDF planifiés, actions de maintenance et interventions terrain opérationnelles ;
- notifications automatiques à la création d’une dépense ou d’une demande (aujourd’hui déclenchées par les services existants) et export comptable des dépenses ;
- notifications SMS/email/in-app reliées à chaque événement métier ;
- gestion UI complète pour l’administration, prix/plans/abonnements, audit et exports ;
- synchronisation offline/PWA avec queue chiffrée, stratégie de conflit et upload différé ;
- tests navigateur/e2e, tests de charge, monitoring produit, alertes et analyse de pièces jointes ;
- validation juridique des CGU, de la politique de confidentialité, des SLA et des prestations.

Le back-office Django permet déjà aux opérateurs autorisés de gérer les principaux modèles. L’interface dashboard expose des actions rapides vers ce back-office plutôt que de prétendre fournir un écran CRUD métier complet pour chaque ressource.
