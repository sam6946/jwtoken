"""Supprime les demandes créées par la recette automatisée.

Le banc d'essai de bout en bout envoie une vraie demande de service pour vérifier
le parcours complet. La suppression côté client étant volontairement interdite
(403), on nettoie ici les demandes de test afin de garder des données de
démonstration propres et rejouables. Les journaux d'audit de ces demandes sont
retirés en même temps : ils resteraient sinon visibles dans l'espace client.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from common.models import AuditLog
from service_requests.models import ServiceRequest

MARKER = "banc d’essai"


class Command(BaseCommand):
    help = "Supprime les demandes de service créées par le banc de recette et leurs journaux d’audit."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Affiche les demandes concernées sans les supprimer.")

    @transaction.atomic
    def handle(self, *args, **options):
        candidates = ServiceRequest.objects.filter(description__icontains=MARKER)
        references = list(candidates.values_list("request_code", flat=True))
        if options["dry_run"]:
            self.stdout.write("Demandes de recette : " + (", ".join(references) if references else "aucune"))
            return

        # Les journaux d'audit des demandes supprimées resteraient visibles dans
        # l'espace client : on retire ceux dont l'objet n'existe plus.
        if references:
            candidates.delete()
        remaining = {str(pk) for pk in ServiceRequest.objects.values_list("pk", flat=True)}
        orphans = AuditLog.objects.filter(event="service_request.created").exclude(object_id__in=remaining)
        removed_logs = orphans.count()
        orphans.delete()

        if references:
            self.stdout.write(f"{len(references)} demande(s) de recette supprimée(s) : " + ", ".join(references))
        else:
            self.stdout.write("Aucune demande de recette à supprimer.")
        if removed_logs:
            self.stdout.write(f"{removed_logs} journal(aux) d’audit orphelin(s) nettoyé(s).")
