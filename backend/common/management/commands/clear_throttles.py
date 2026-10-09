"""Réinitialise les compteurs anti-abus de l'API.

Les limites (connexions, demandes de service, codes OTP) protègent la plateforme
en production. En développement, la recette automatisée envoie plusieurs requêtes
d'affilée : cette commande remet les compteurs à zéro.

Refus par défaut en mode production (DEBUG=False) pour éviter tout usage abusif.
"""
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Réinitialise les compteurs de limitation de débit (throttling) de l'API."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Autorise l'exécution même en production.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "Commande refusée : l'API n'est pas en mode développement. Utilisez --force en connaissance de cause."
            )
        if hasattr(cache, "delete_pattern"):
            removed = cache.delete_pattern("*throttle*")
            self.stdout.write(f"Compteurs de limitation réinitialisés ({removed} clé(s)).")
            return
        cache.clear()
        self.stdout.write("Cache local vidé : compteurs de limitation réinitialisés.")
