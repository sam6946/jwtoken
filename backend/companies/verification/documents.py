"""Validation, stockage et complétude des pièces entreprise.

Les fichiers ne sont jamais exposés depuis ce module. L'autorisation de leur
consultation reste concentrée dans la vue privée dédiée.
"""
from pathlib import Path
from typing import Any

from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from common.services import write_audit_event
from companies.models import (
    CompanyDocument,
    CompanyDocumentStatus,
    CompanyDocumentType,
    CompanyProfile,
)
from companies.verification.constants import (
    ALLOWED_DOCUMENT_SUFFIXES,
    DOCUMENT_REQUIREMENTS,
    MAX_DOCUMENT_SIZE,
    PROFILE_REQUIRED_FIELDS,
)


def validate_document_file(file_obj: Any) -> None:
    """Valide le type, la taille et la signature du fichier avant stockage."""
    suffix = Path(file_obj.name or "").suffix.lower()
    allowed_types = ALLOWED_DOCUMENT_SUFFIXES.get(suffix)
    if not allowed_types or file_obj.content_type not in allowed_types:
        raise ValidationError({"file": "Seuls les fichiers JPG, PNG, WebP et PDF sont autorisés."})
    if file_obj.size <= 0 or file_obj.size > MAX_DOCUMENT_SIZE:
        raise ValidationError({"file": "Chaque document doit peser entre 1 octet et 8 Mo."})

    file_obj.seek(0)
    if suffix == ".pdf":
        if file_obj.read(5) != b"%PDF-":
            raise ValidationError({"file": "Le fichier PDF transmis n’est pas valide."})
    else:
        try:
            with Image.open(file_obj) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError({"file": "L’image transmise n’est pas valide."}) from exc
    file_obj.seek(0)


def document_label(document_type: str) -> str:
    """Retourne le libellé métier d'un type de pièce valide."""
    return str(CompanyDocumentType(document_type).label)


def required_document_types() -> tuple[str, ...]:
    """Types de pièces obligatoires, dans leur ordre d'affichage."""
    return tuple(document_type for document_type, required in DOCUMENT_REQUIREMENTS if required)


def documents_by_type(company: CompanyProfile) -> dict[str, CompanyDocument]:
    """Indexe les pièces préchargées ou liées à une entreprise par leur type."""
    return {document.document_type: document for document in company.documents.all()}


def missing_profile_fields(company: CompanyProfile) -> list[str]:
    """Libellés des informations obligatoires encore absentes."""
    missing = []
    for field, label in PROFILE_REQUIRED_FIELDS:
        value = (getattr(company, field) or "").strip()
        if not value:
            missing.append(label)
    if not (company.name or "").strip():
        missing.append("Nom commercial")
    return missing


def missing_document_labels(company: CompanyProfile) -> list[str]:
    """Libellés des pièces indispensables qui n'ont pas encore été déposées."""
    present = documents_by_type(company)
    return [
        document_label(document_type)
        for document_type in required_document_types()
        if document_type not in present
    ]


def can_submit(company: CompanyProfile) -> bool:
    """Indique si profil et pièces obligatoires permettent une soumission."""
    return not missing_profile_fields(company) and not missing_document_labels(company)


def store_document(
    *,
    company: CompanyProfile,
    document_type: str,
    file_obj: Any,
    actor: Any,
    expires_at: Any = None,
    request_id: str = "",
) -> CompanyDocument:
    """Ajoute ou remplace une pièce ; un type ne possède qu'un document courant."""
    validate_document_file(file_obj)
    document = CompanyDocument.objects.filter(company=company, document_type=document_type).first()
    if document is None:
        document = CompanyDocument(company=company, document_type=document_type)

    document.file = file_obj
    document.original_name = Path(file_obj.name or "").name[:255]
    document.content_type = (file_obj.content_type or "")[:120]
    document.file_size = file_obj.size
    document.status = CompanyDocumentStatus.PENDING
    document.rejection_reason = ""
    document.uploaded_at = timezone.now()
    document.reviewed_at = None
    document.reviewed_by = None
    if expires_at is not None:
        document.expires_at = expires_at
    document.save()

    # Le remplacement d'une pièce ne rétrograde pas automatiquement une décision
    # explicite KEMTA : seul un examen administrateur peut modifier ce statut.
    write_audit_event(
        event="company.document_uploaded",
        actor=actor,
        object_type="company_document",
        object_id=document.pk,
        metadata={"document_type": document.document_type, "file_size": document.file_size},
        request_id=request_id,
    )
    return document
