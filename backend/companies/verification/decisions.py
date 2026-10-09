"""Soumission et décisions KEMTA sur un dossier entreprise.

Toute transition qui produit un audit ou une notification est regroupée ici ;
les vues restent de simples adaptateurs HTTP.
"""
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import UserRole
from common.services import write_audit_event
from companies.models import (
    CompanyDocument,
    CompanyDocumentStatus,
    CompanyDocumentType,
    CompanyProfile,
    CompanyVerificationStatus,
)
from companies.verification.constants import ADMIN_ACTION_URL, DECISION_ACTIONS, OWNER_ACTION_URL
from companies.verification.documents import (
    document_label,
    documents_by_type,
    missing_document_labels,
    missing_profile_fields,
)
from notifications.models import NotificationType
from notifications.services import create_in_app_notification


def _notify(
    user: Any,
    *,
    title: str,
    body: str,
    action_url: str,
    dedupe_key: str | None = None,
) -> None:
    """Utilise le canal de notification existant, avec une clé anti-doublon."""
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
        type(company.user)
        .objects.filter(
            role__in=(UserRole.ADMIN, UserRole.SUPER_ADMIN),
            is_active=True,
        )
        .only("id", "phone")
        .iterator()
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
def submit_verification(
    company: CompanyProfile,
    actor: Any,
    request_id: str = "",
) -> CompanyProfile:
    """Soumet un dossier complet et prévient l'entreprise comme les réviseurs."""
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
    CompanyDocument.objects.filter(
        company=company,
        status=CompanyDocumentStatus.REJECTED,
    ).update(
        status=CompanyDocumentStatus.PENDING,
        rejection_reason="",
        updated_at=timezone.now(),
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
    _notify_reviewers(
        company,
        dedupe_key=f"company-submitted-{company.pk}-{company.verification_submitted_at.isoformat()}",
    )
    return company


@transaction.atomic
def _record_decision(
    company: CompanyProfile,
    actor: Any,
    *,
    status: str,
    reason: str = "",
    request_id: str = "",
) -> CompanyProfile:
    """Persiste les champs communs à toutes les décisions explicites KEMTA."""
    company.verification_status = status
    company.verification_rejection_reason = reason
    company.verification_reviewed_at = timezone.now()
    company.verification_reviewed_by = actor
    company.save()
    return company


@transaction.atomic
def start_review(company: CompanyProfile, actor: Any, request_id: str = "") -> CompanyProfile:
    """Marque un dossier en attente comme en cours de revue."""
    if company.verification_status not in {
        CompanyVerificationStatus.PENDING,
        CompanyVerificationStatus.UNDER_REVIEW,
    }:
        raise ValidationError({"detail": "Aucun dossier en attente d’examen pour cette entreprise."})
    company.verification_status = CompanyVerificationStatus.UNDER_REVIEW
    company.save(update_fields=("verification_status", "verification_level", "updated_at"))
    write_audit_event(
        event="company.review_started",
        actor=actor,
        object_type="company_profile",
        object_id=company.pk,
        request_id=request_id,
    )
    return company


@transaction.atomic
def approve_verification(
    company: CompanyProfile,
    actor: Any,
    *,
    advanced: bool = False,
    request_id: str = "",
) -> CompanyProfile:
    """Approuve le dossier et les pièces déposées, puis notifie l'entreprise."""
    was_verified = company.verification_status == CompanyVerificationStatus.VERIFIED
    company.advanced_verified = bool(advanced) or company.advanced_verified
    _record_decision(
        company,
        actor,
        status=CompanyVerificationStatus.VERIFIED,
        reason="",
        request_id=request_id,
    )
    CompanyDocument.objects.filter(company=company).update(
        status=CompanyDocumentStatus.APPROVED,
        rejection_reason="",
        reviewed_at=timezone.now(),
        reviewed_by=actor,
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


def _validated_reason(reason: str, message: str) -> str:
    """Normalise un motif obligatoire avant toute décision négative."""
    normalized = (reason or "").strip()
    if len(normalized) < 5:
        raise ValidationError({"reason": message})
    return normalized


@transaction.atomic
def reject_verification(
    company: CompanyProfile,
    actor: Any,
    *,
    reason: str,
    request_id: str = "",
) -> CompanyProfile:
    """Refuse le dossier complet avec un motif consultable par l'entreprise."""
    reason = _validated_reason(reason, "Indiquez le motif du refus (au moins 5 caractères).")
    _record_decision(
        company,
        actor,
        status=CompanyVerificationStatus.REJECTED,
        reason=reason,
        request_id=request_id,
    )
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
def request_correction(
    company: CompanyProfile,
    actor: Any,
    *,
    reason: str,
    document_type: str = "",
    request_id: str = "",
) -> CompanyProfile:
    """Demande une correction ciblée : seule la pièce visée doit être remplacée."""
    reason = _validated_reason(reason, "Indiquez la correction attendue (au moins 5 caractères).")
    document = None
    if document_type:
        try:
            CompanyDocumentType(document_type)
        except ValueError as exc:
            raise ValidationError({"document_type": "Type de document inconnu."}) from exc
        document = CompanyDocument.objects.filter(
            company=company,
            document_type=document_type,
        ).first()
        if document is None:
            raise ValidationError({"document_type": "Aucun document de ce type n’a été envoyé."})

    _record_decision(
        company,
        actor,
        status=CompanyVerificationStatus.REJECTED,
        reason=reason,
        request_id=request_id,
    )
    if document is not None:
        document.status = CompanyDocumentStatus.REJECTED
        document.rejection_reason = reason
        document.reviewed_at = timezone.now()
        document.reviewed_by = actor
        document.save(
            update_fields=(
                "status",
                "rejection_reason",
                "reviewed_at",
                "reviewed_by",
                "updated_at",
            )
        )
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
        dedupe_key=(
            f"company-correction-{company.pk}-"
            f"{company.verification_reviewed_at.isoformat()}-{document_type}"
        ),
    )
    return company


@transaction.atomic
def suspend_verification(
    company: CompanyProfile,
    actor: Any,
    *,
    reason: str,
    request_id: str = "",
) -> CompanyProfile:
    """Suspend une entreprise, ce qui retire sa publication via le modèle."""
    reason = _validated_reason(reason, "Indiquez le motif de la suspension (au moins 5 caractères).")
    _record_decision(
        company,
        actor,
        status=CompanyVerificationStatus.SUSPENDED,
        reason=reason,
        request_id=request_id,
    )
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


def reviewer_can_decide(user: Any) -> bool:
    """Indique si un compte appartient à l'équipe KEMTA autorisée à décider."""
    return bool(
        user.is_authenticated
        and (user.is_staff or user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN})
    )


def apply_decision(
    company: CompanyProfile,
    actor: Any,
    *,
    action: str,
    reason: str = "",
    document_type: str = "",
    advanced: bool = False,
    request_id: str = "",
) -> CompanyProfile:
    """Point d'entrée unique des décisions administratives supportées."""
    if action not in DECISION_ACTIONS:
        values = ", ".join(DECISION_ACTIONS)
        raise ValidationError({"action": f"Action inconnue. Valeurs possibles : {values}."})
    if action == "start_review":
        return start_review(company, actor, request_id=request_id)
    if action == "approve":
        return approve_verification(company, actor, advanced=advanced, request_id=request_id)
    if action == "reject":
        return reject_verification(company, actor, reason=reason, request_id=request_id)
    if action == "request_correction":
        return request_correction(
            company,
            actor,
            reason=reason,
            document_type=document_type,
            request_id=request_id,
        )
    return suspend_verification(company, actor, reason=reason, request_id=request_id)


def review_queue(limit: int | None = None):
    """Dossiers à traiter, du plus ancien au plus récent."""
    queryset = (
        CompanyProfile.objects.filter(
            verification_status__in=(
                CompanyVerificationStatus.PENDING,
                CompanyVerificationStatus.UNDER_REVIEW,
            )
        )
        .select_related("user")
        .prefetch_related("documents")
        .order_by("verification_submitted_at", "created_at")
    )
    return queryset[:limit] if limit else queryset
