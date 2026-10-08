"""Règles du dossier de vérification des entreprises.

Tout le parcours (complétude du profil, dépôt des pièces, soumission, examen,
décision) est réuni ici pour rester cohérent entre l'espace entreprise,
l'administration, les notifications et l'audit.

Les notifications et l'audit passent par les services déjà en place
(`notifications.services`, `common.services`) : aucun second système n'est créé.
"""
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from accounts.models import UserRole
from common.services import write_audit_event
from companies.models import (
    CompanyDocument,
    CompanyDocumentStatus,
    CompanyDocumentType,
    CompanyProfile,
    CompanyVerificationLevel,
    CompanyVerificationStatus,
)
from notifications.models import NotificationType
from notifications.services import create_in_app_notification

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

ALLOWED_DOCUMENT_SUFFIXES = {".pdf": {"application/pdf"}, ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}, ".png": {"image/png"}, ".webp": {"image/webp"}}
MAX_DOCUMENT_SIZE = 8 * 1024 * 1024

OWNER_ACTION_URL = "/entreprise/verification"
ADMIN_ACTION_URL = "/dashboard#admin-verifications"

DECISION_ACTIONS = ("start_review", "approve", "reject", "request_correction", "suspend")


def validate_document_file(file_obj) -> None:
    """Mêmes règles que les autres pièces de la plateforme : nature et taille."""
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
    return str(CompanyDocumentType(document_type).label)


def required_document_types() -> tuple[str, ...]:
    return tuple(document_type for document_type, required in DOCUMENT_REQUIREMENTS if required)


def documents_by_type(company: CompanyProfile) -> dict[str, CompanyDocument]:
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
    present = documents_by_type(company)
    return [document_label(document_type) for document_type in required_document_types() if document_type not in present]


def can_submit(company: CompanyProfile) -> bool:
    return not missing_profile_fields(company) and not missing_document_labels(company)


def document_checklist(company: CompanyProfile) -> list[dict]:
    """État de chaque pièce attendue, tel qu'affiché dans le parcours."""
    present = documents_by_type(company)
    checklist = []
    for document_type, required in DOCUMENT_REQUIREMENTS:
        document = present.get(document_type)
        file_name = ""
        if document is not None:
            file_name = document.original_name or document.file.name.rsplit("/", 1)[-1]
        checklist.append({
            "document_type": document_type,
            "label": document_label(document_type),
            "required": required,
            "state": document.status if document else "MISSING",
            "document_id": document.pk if document else None,
            "file_name": file_name,
            "uploaded_at": document.uploaded_at if document else None,
            "rejection_reason": document.rejection_reason if document else "",
        })
    return checklist


def verification_checklist(company: CompanyProfile, user) -> list[dict]:
    """Les cinq étapes du parcours, avec leur état."""
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
            "state": "DONE" if verified else "REJECTED" if status == CompanyVerificationStatus.REJECTED else "IN_REVIEW" if company.verification_in_review else "PENDING",
        },
    ]


def verification_snapshot(company: CompanyProfile, user) -> dict:
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
        "ready_for_review": company.verification_in_review or company.verification_status == CompanyVerificationStatus.VERIFIED,
        "missing_profile_fields": missing_profile_fields(company),
        "missing_documents": missing_document_labels(company),
        "checklist": verification_checklist(company, user),
        "documents": document_checklist(company),
    }


def _notify(user, *, title: str, body: str, action_url: str, dedupe_key: str | None = None) -> None:
    create_in_app_notification(
        user=user,
        title=title,
        body=body,
        notification_type=NotificationType.GENERAL,
        action_url=action_url,
        data={"company": "verification"},
        dedupe_key=dedupe_key,
    )


def _notify_reviewers(company: CompanyProfile, *, dedupe_key: str | None = None) -> None:
    """Prévient l'équipe KEMTA qu'un dossier attend son examen."""
    reviewers = (
        type(company.user).objects.filter(role__in=(UserRole.ADMIN, UserRole.SUPER_ADMIN), is_active=True)
        .only("id", "phone").iterator()
    )
    for reviewer in reviewers:
        _notify(
            reviewer,
            title="Nouvelle entreprise à vérifier",
            body=f"{company.name} a envoyé son dossier de vérification.",
            action_url=ADMIN_ACTION_URL,
            dedupe_key=dedupe_key,
        )


@transaction.atomic
def submit_verification(company: CompanyProfile, actor, request_id: str = "") -> CompanyProfile:
    """Soumet le dossier : le profil et les pièces exigées doivent être complets."""
    if company.verification_status == CompanyVerificationStatus.VERIFIED:
        raise ValidationError({"detail": "Votre entreprise est déjà vérifiée."})
    if company.verification_in_review:
        raise ValidationError({"detail": "Votre dossier est déjà en cours d’examen."})
    missing_fields = missing_profile_fields(company)
    if missing_fields:
        raise ValidationError({"profile": f"Complétez d’abord : {', '.join(missing_fields)}."})
    missing_documents = missing_document_labels(company)
    if missing_documents:
        raise ValidationError({"documents": f"Ajoutez les documents requis : {', '.join(missing_documents)}."})

    company.verification_status = CompanyVerificationStatus.PENDING
    company.verification_submitted_at = timezone.now()
    company.verification_rejection_reason = ""
    company.verification_reviewed_at = None
    company.verification_reviewed_by = None
    company.save()
    CompanyDocument.objects.filter(company=company, status=CompanyDocumentStatus.REJECTED).update(
        status=CompanyDocumentStatus.PENDING, rejection_reason="", updated_at=timezone.now()
    )

    write_audit_event(
        event="company.verification_submitted",
        actor=actor,
        object_type="company_profile",
        object_id=company.pk,
        metadata={"documents": len(documents_by_type(company))},
        request_id=request_id,
    )
    _notify(
        company.user,
        title="Dossier de vérification envoyé",
        body="Notre équipe examine les informations de votre entreprise. Vous serez notifié de la décision.",
        action_url=OWNER_ACTION_URL,
    )
    _notify_reviewers(company, dedupe_key=f"company-submitted-{company.pk}-{company.verification_submitted_at.isoformat()}")
    return company


@transaction.atomic
def _record_decision(company: CompanyProfile, actor, *, status: str, reason: str = "", request_id: str = "") -> CompanyProfile:
    company.verification_status = status
    company.verification_rejection_reason = reason
    company.verification_reviewed_at = timezone.now()
    company.verification_reviewed_by = actor
    company.save()
    return company


@transaction.atomic
def start_review(company: CompanyProfile, actor, request_id: str = "") -> CompanyProfile:
    if company.verification_status not in {CompanyVerificationStatus.PENDING, CompanyVerificationStatus.UNDER_REVIEW}:
        raise ValidationError({"detail": "Aucun dossier en attente d’examen pour cette entreprise."})
    company.verification_status = CompanyVerificationStatus.UNDER_REVIEW
    company.save(update_fields=("verification_status", "verification_level", "updated_at"))
    write_audit_event(event="company.review_started", actor=actor, object_type="company_profile", object_id=company.pk, request_id=request_id)
    return company


@transaction.atomic
def approve_verification(company: CompanyProfile, actor, *, advanced: bool = False, request_id: str = "") -> CompanyProfile:
    was_verified = company.verification_status == CompanyVerificationStatus.VERIFIED
    company.advanced_verified = bool(advanced) or company.advanced_verified
    _record_decision(company, actor, status=CompanyVerificationStatus.VERIFIED, reason="", request_id=request_id)
    CompanyDocument.objects.filter(company=company).update(
        status=CompanyDocumentStatus.APPROVED, rejection_reason="", reviewed_at=timezone.now(), reviewed_by=actor
    )
    write_audit_event(
        event="company.verified",
        actor=actor,
        object_type="company_profile",
        object_id=company.pk,
        metadata={"advanced": company.advanced_verified},
        request_id=request_id,
    )
    for document in company.documents.all():
        write_audit_event(
            event="company.document_approved",
            actor=actor,
            object_type="company_document",
            object_id=document.pk,
            metadata={"document_type": document.document_type},
            request_id=request_id,
        )
    if not was_verified:
        _notify(
            company.user,
            title="Entreprise vérifiée",
            body="Votre entreprise a été vérifiée par KEMTA. Vous accédez maintenant aux fonctionnalités professionnelles.",
            action_url=OWNER_ACTION_URL,
            dedupe_key=f"company-verified-{company.pk}",
        )
    return company


@transaction.atomic
def reject_verification(company: CompanyProfile, actor, *, reason: str, request_id: str = "") -> CompanyProfile:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"reason": "Indiquez le motif du refus (au moins 5 caractères)."})
    _record_decision(company, actor, status=CompanyVerificationStatus.REJECTED, reason=reason, request_id=request_id)
    write_audit_event(
        event="company.verification_rejected",
        actor=actor,
        object_type="company_profile",
        object_id=company.pk,
        metadata={"reason": reason},
        request_id=request_id,
    )
    _notify(
        company.user,
        title="Vérification non validée",
        body=f"Motif : {reason}",
        action_url=OWNER_ACTION_URL,
        dedupe_key=f"company-rejected-{company.pk}-{company.verification_reviewed_at.isoformat()}",
    )
    return company


@transaction.atomic
def request_correction(company: CompanyProfile, actor, *, reason: str, document_type: str = "", request_id: str = "") -> CompanyProfile:
    """Demande une correction ciblée : seule la pièce visée doit être remplacée."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"reason": "Indiquez la correction attendue (au moins 5 caractères)."})
    document = None
    if document_type:
        try:
            CompanyDocumentType(document_type)
        except ValueError as exc:
            raise ValidationError({"document_type": "Type de document inconnu."}) from exc
        document = CompanyDocument.objects.filter(company=company, document_type=document_type).first()
        if document is None:
            raise ValidationError({"document_type": "Aucun document de ce type n’a été envoyé."})

    _record_decision(company, actor, status=CompanyVerificationStatus.REJECTED, reason=reason, request_id=request_id)
    if document is not None:
        document.status = CompanyDocumentStatus.REJECTED
        document.rejection_reason = reason
        document.reviewed_at = timezone.now()
        document.reviewed_by = actor
        document.save(update_fields=("status", "rejection_reason", "reviewed_at", "reviewed_by", "updated_at"))
        write_audit_event(
            event="company.document_rejected",
            actor=actor,
            object_type="company_document",
            object_id=document.pk,
            metadata={"document_type": document.document_type, "reason": reason},
            request_id=request_id,
        )
    write_audit_event(
        event="company.correction_requested",
        actor=actor,
        object_type="company_profile",
        object_id=company.pk,
        metadata={"document_type": document_type or "", "reason": reason},
        request_id=request_id,
    )
    target = f" ({document_label(document_type)})" if document_type else ""
    _notify(
        company.user,
        title=f"Correction demandée{target}",
        body=f"Motif : {reason}",
        action_url=OWNER_ACTION_URL,
        dedupe_key=f"company-correction-{company.pk}-{company.verification_reviewed_at.isoformat()}-{document_type}",
    )
    return company


@transaction.atomic
def suspend_verification(company: CompanyProfile, actor, *, reason: str, request_id: str = "") -> CompanyProfile:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"reason": "Indiquez le motif de la suspension (au moins 5 caractères)."})
    _record_decision(company, actor, status=CompanyVerificationStatus.SUSPENDED, reason=reason, request_id=request_id)
    write_audit_event(
        event="company.suspended",
        actor=actor,
        object_type="company_profile",
        object_id=company.pk,
        metadata={"reason": reason},
        request_id=request_id,
    )
    _notify(
        company.user,
        title="Vérification suspendue",
        body=f"Motif : {reason}",
        action_url=OWNER_ACTION_URL,
        dedupe_key=f"company-suspended-{company.pk}-{company.verification_reviewed_at.isoformat()}",
    )
    return company


@transaction.atomic
def store_document(*, company: CompanyProfile, document_type: str, file_obj, actor, expires_at=None, request_id: str = "") -> CompanyDocument:
    """Ajoute ou remplace la pièce d'un type donné (un seul document par type)."""
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

    if company.verification_status in {CompanyVerificationStatus.VERIFIED, CompanyVerificationStatus.SUSPENDED}:
        # Une pièce mise à jour après vérification ne remet pas le statut en cause.
        pass
    write_audit_event(
        event="company.document_uploaded",
        actor=actor,
        object_type="company_document",
        object_id=document.pk,
        metadata={"document_type": document.document_type, "file_size": document.file_size},
        request_id=request_id,
    )
    return document


def reviewer_can_decide(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}))


def apply_decision(company: CompanyProfile, actor, *, action: str, reason: str = "", document_type: str = "", advanced: bool = False, request_id: str = "") -> CompanyProfile:
    """Point d'entrée unique des décisions d'administration."""
    if action not in DECISION_ACTIONS:
        raise ValidationError({"action": f"Action inconnue. Valeurs possibles : {', '.join(DECISION_ACTIONS)}."})
    if action == "start_review":
        return start_review(company, actor, request_id=request_id)
    if action == "approve":
        return approve_verification(company, actor, advanced=advanced, request_id=request_id)
    if action == "reject":
        return reject_verification(company, actor, reason=reason, request_id=request_id)
    if action == "request_correction":
        return request_correction(company, actor, reason=reason, document_type=document_type, request_id=request_id)
    return suspend_verification(company, actor, reason=reason, request_id=request_id)


def review_queue(limit: int | None = None):
    """Dossiers à traiter, du plus ancien au plus récent."""
    queryset = (
        CompanyProfile.objects.filter(
            verification_status__in=(CompanyVerificationStatus.PENDING, CompanyVerificationStatus.UNDER_REVIEW)
        )
        .select_related("user")
        .prefetch_related("documents")
        .order_by("verification_submitted_at", "created_at")
    )
    return queryset[:limit] if limit else queryset


def level_progress(company: CompanyProfile) -> list[dict]:
    """Les quatre niveaux, pour situer l'entreprise dans le parcours."""
    order = (
        CompanyVerificationLevel.ACCOUNT,
        CompanyVerificationLevel.PROFILE,
        CompanyVerificationLevel.BUSINESS_VERIFIED,
        CompanyVerificationLevel.ADVANCED,
    )
    current_index = order.index(company.verification_level) if company.verification_level in order else 0
    return [
        {"level": level, "label": str(CompanyVerificationLevel(level).label), "reached": index <= current_index}
        for index, level in enumerate(order)
    ]
