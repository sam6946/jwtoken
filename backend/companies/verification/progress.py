"""Représentations de progression consommées par l'espace entreprise.

Les dictionnaires produits ici restent volontairement compatibles avec les
serializers et l'interface existante : ce module ne décide pas du statut.
"""
from typing import Any

from companies.models import (
    CompanyProfile,
    CompanyVerificationLevel,
    CompanyVerificationStatus,
)
from companies.verification.constants import DOCUMENT_REQUIREMENTS
from companies.verification.documents import (
    can_submit,
    document_label,
    documents_by_type,
    missing_document_labels,
    missing_profile_fields,
)


def document_checklist(company: CompanyProfile) -> list[dict[str, Any]]:
    """État de chaque pièce attendue, dans l'ordre du parcours."""
    present = documents_by_type(company)
    checklist: list[dict[str, Any]] = []
    for document_type, required in DOCUMENT_REQUIREMENTS:
        document = present.get(document_type)
        file_name = ""
        if document is not None:
            file_name = document.original_name or document.file.name.rsplit("/", 1)[-1]
        checklist.append(
            {
                "document_type": document_type,
                "label": document_label(document_type),
                "required": required,
                "state": document.status if document else "MISSING",
                "document_id": document.pk if document else None,
                "file_name": file_name,
                "uploaded_at": document.uploaded_at if document else None,
                "rejection_reason": document.rejection_reason if document else "",
            }
        )
    return checklist


def verification_checklist(company: CompanyProfile, user: Any) -> list[dict[str, str]]:
    """Les cinq étapes du parcours, avec leur état courant."""
    profile_ready = not missing_profile_fields(company)
    documents_ready = not missing_document_labels(company)
    status = company.verification_status
    verified = status == CompanyVerificationStatus.VERIFIED
    return [
        {"key": "ACCOUNT", "label": "Compte créé", "state": "DONE"},
        {"key": "PHONE", "label": "Téléphone vérifié", "state": "DONE" if user.phone_verified else "PENDING"},
        {"key": "PROFILE", "label": "Profil entreprise", "state": "DONE" if profile_ready else "PENDING"},
        {"key": "DOCUMENTS", "label": "Documents envoyés", "state": "DONE" if documents_ready else "PENDING"},
        {
            "key": "REVIEW",
            "label": "Vérification KEMTA",
            "state": (
                "DONE"
                if verified
                else "REJECTED"
                if status == CompanyVerificationStatus.REJECTED
                else "IN_REVIEW"
                if company.verification_in_review
                else "PENDING"
            ),
        },
    ]


def verification_snapshot(company: CompanyProfile, user: Any) -> dict[str, Any]:
    """Charge utile complète du dossier pour l'espace entreprise."""
    return {
        "company_id": company.pk,
        "company_name": company.name,
        "status": company.verification_status,
        "status_label": company.get_verification_status_display(),
        "level": company.verification_level,
        "level_label": company.get_verification_level_display(),
        "verified": company.verified,
        "is_published": company.is_published,
        "advanced_verified": company.advanced_verified,
        "submitted_at": company.verification_submitted_at,
        "reviewed_at": company.verification_reviewed_at,
        "rejection_reason": company.verification_rejection_reason,
        "can_submit": can_submit(company),
        "ready_for_review": (
            company.verification_in_review
            or company.verification_status == CompanyVerificationStatus.VERIFIED
        ),
        "missing_profile_fields": missing_profile_fields(company),
        "missing_documents": missing_document_labels(company),
        "checklist": verification_checklist(company, user),
        "documents": document_checklist(company),
    }


def level_progress(company: CompanyProfile) -> list[dict[str, Any]]:
    """Les quatre niveaux, afin de situer l'entreprise dans le parcours."""
    order = (
        CompanyVerificationLevel.ACCOUNT,
        CompanyVerificationLevel.PROFILE,
        CompanyVerificationLevel.BUSINESS_VERIFIED,
        CompanyVerificationLevel.ADVANCED,
    )
    current_index = order.index(company.verification_level) if company.verification_level in order else 0
    return [
        {
            "level": level,
            "label": str(CompanyVerificationLevel(level).label),
            "reached": index <= current_index,
        }
        for index, level in enumerate(order)
    ]
