"""Supprime les demandes créées par la recette automatisée.

Le banc d'essai de bout en bout envoie une vraie demande de service pour vérifier
le parcours complet. La suppression côté client étant volontairement interdite
(403), on nettoie ici les demandes de test afin de garder des données de
démonstration propres et rejouables.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from service_requests.models import ServiceRequest

MARKER = "banc d’essai"


class Command(BaseCommand):
    help = "Supprime les demandes de service créées par le banc de recette."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Affiche les demandes concernées sans les supprimer.")

    @transaction.atomic
    def handle(self, *args, **options):
        candidates = ServiceRequest.objects.filter(description__icontains=MARKER)
        references = list(candidates.values_list("request_code", flat=True))
        if not references:
            self.stdout.write("Aucune demande de recette à supprimer.")
            return
        if options["dry_run"]:
            self.stdout.write("Demandes de recette : " + ", ".join(references))
            return
        candidates.delete()
        self.stdout.write(f"{len(references)} demande(s) de recette supprimée(s) : " + ", ".join(references))
