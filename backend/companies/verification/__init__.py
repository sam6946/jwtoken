"""Façade publique du domaine de vérification entreprise.

Les imports historiques ``from companies import verification`` restent valides.
La logique est répartie par responsabilité dans :

* ``constants`` : règles et valeurs stables ;
* ``documents`` : validation, stockage et complétude des pièces ;
* ``progress`` : checklist et état présenté à l'entreprise ;
* ``decisions`` : soumission, décisions, audit et notifications.
"""
from companies.verification.constants import (
    ADMIN_ACTION_URL,
    ALLOWED_DOCUMENT_SUFFIXES,
    DECISION_ACTIONS,
    DOCUMENT_REQUIREMENTS,
    MAX_DOCUMENT_SIZE,
    OWNER_ACTION_URL,
    PROFILE_REQUIRED_FIELDS,
)
from companies.verification.decisions import (
    apply_decision,
    approve_verification,
    reject_verification,
    request_correction,
    review_queue,
    reviewer_can_decide,
    start_review,
    submit_verification,
    suspend_verification,
)
from companies.verification.documents import (
    can_submit,
    document_label,
    documents_by_type,
    missing_document_labels,
    missing_profile_fields,
    required_document_types,
    store_document,
    validate_document_file,
)
from companies.verification.progress import (
    document_checklist,
    level_progress,
    verification_checklist,
    verification_snapshot,
)

__all__ = (
    "ADMIN_ACTION_URL",
    "ALLOWED_DOCUMENT_SUFFIXES",
    "DECISION_ACTIONS",
    "DOCUMENT_REQUIREMENTS",
    "MAX_DOCUMENT_SIZE",
    "OWNER_ACTION_URL",
    "PROFILE_REQUIRED_FIELDS",
    "apply_decision",
    "approve_verification",
    "can_submit",
    "document_checklist",
    "document_label",
    "documents_by_type",
    "level_progress",
    "missing_document_labels",
    "missing_profile_fields",
    "reject_verification",
    "request_correction",
    "required_document_types",
    "review_queue",
    "reviewer_can_decide",
    "start_review",
    "store_document",
    "submit_verification",
    "suspend_verification",
    "validate_document_file",
    "verification_checklist",
    "verification_snapshot",
)
