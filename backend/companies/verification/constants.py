"""Constantes stables du parcours de vérification entreprise.

Ce module ne contient aucune logique métier : il centralise les règles visibles
par l'API et l'interface afin que leur ordre et leurs libellés restent stables.
"""
from companies.models import CompanyDocumentType

# Pièces affichées dans l'ordre du parcours. `True` = pièce exigée pour soumettre.
DOCUMENT_REQUIREMENTS: tuple[tuple[str, bool], ...] = (
    (CompanyDocumentType.RCCM, True),
    (CompanyDocumentType.NIU, True),
    (CompanyDocumentType.REGISTRATION_CERTIFICATE, False),
    (CompanyDocumentType.IDENTITY_DOCUMENT, True),
    (CompanyDocumentType.ADDRESS_PROOF, False),
)

# Champs du profil exigés avant de soumettre le dossier.
PROFILE_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ("legal_name", "Nom légal"),
    ("company_type", "Type d’entreprise"),
    ("sector", "Secteur d’activité"),
    ("city", "Ville"),
    ("address", "Adresse"),
)

ALLOWED_DOCUMENT_SUFFIXES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
}
MAX_DOCUMENT_SIZE = 8 * 1024 * 1024

OWNER_ACTION_URL = "/entreprise/verification"
ADMIN_ACTION_URL = "/dashboard#admin-verifications"

DECISION_ACTIONS: tuple[str, ...] = (
    "start_review",
    "approve",
    "reject",
    "request_correction",
    "suspend",
)
