"""Règles métier du pilotage terrain KEMTA.

Les vues HTTP ne font qu'authentifier et sérialiser. Toutes les transitions de
mission et de rapport passent ici afin de garder le même comportement depuis
le dashboard, l'API mobile et une éventuelle reprise hors connexion.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from common.services import write_audit_event
from notifications.models import NotificationType
from notifications.services import create_in_app_notification
from projects.models import (
    FieldMission,
    FieldReport,
    FieldReportStatus,
    MissionStatus,
    Project,
    ProjectAssignment,
    ProjectAssignmentStatus,
)


MANAGER_DASHBOARD_URL = "/dashboard#missions"
AGENT_DASHBOARD_URL = "/dashboard#mes-missions"


def _actor_name(actor: Any) -> str:
    return f"{actor.first_name} {actor.last_name}".strip() or actor.phone


def _notify(user: Any, *, title: str, body: str, action_url: str, dedupe_key: str) -> None:
    """Envoie une notification in-app via le service central existant."""
    create_in_app_notification(
        user=user,
        title=title,
        body=body,
        notification_type=NotificationType.TASK,
        action_url=action_url,
        data={"field_work": True},
        dedupe_key=dedupe_key,
    )


def is_active_assignment(project: Project, user: Any) -> bool:
    """Indique si un agent possède une affectation terrain actuellement active."""
    return ProjectAssignment.objects.filter(
        project=project,
        user=user,
        status=ProjectAssignmentStatus.ACTIVE,
    ).exists()


@transaction.atomic
def assign_agent(
    *,
    project: Project,
    agent: Any,
    actor: Any,
    start_date=None,
    end_date=None,
    request_id: str = "",
) -> ProjectAssignment:
    """Crée ou réactive une affectation et conserve le lien historique du projet.

    `Project.field_agents` reste la source de compatibilité des écrans et APIs
    existants. L'affectation enrichit ce lien avec ses dates et son statut.
    """
    assignment, created = ProjectAssignment.objects.get_or_create(
        project=project,
        user=agent,
        role=ProjectAssignment.Role.FIELD_AGENT,
        defaults={
            "assigned_by": actor,
            "start_date": start_date or timezone.localdate(),
            "end_date": end_date,
            "status": ProjectAssignmentStatus.ACTIVE,
        },
    )
    if not created:
        assignment.assigned_by = actor
        assignment.start_date = start_date or assignment.start_date or timezone.localdate()
        assignment.end_date = end_date
        assignment.status = ProjectAssignmentStatus.ACTIVE
        assignment.save(update_fields=("assigned_by", "start_date", "end_date", "status", "updated_at"))
    project.field_agents.add(agent)
    write_audit_event(
        event="project.assignment_created" if created else "project.assignment_reactivated",
        actor=actor,
        object_type="project_assignment",
        object_id=assignment.pk,
        metadata={"project_id": project.pk, "agent_id": agent.pk},
        request_id=request_id,
    )
    return assignment


@transaction.atomic
def create_mission(*, actor: Any, request_id: str = "", **values: Any) -> FieldMission:
    """Crée une mission planifiée et notifie l'agent affecté."""
    project = values["project"]
    assigned_to = values["assigned_to"]
    if not is_active_assignment(project, assigned_to):
        assign_agent(project=project, agent=assigned_to, actor=actor, request_id=request_id)
    mission = FieldMission.objects.create(created_by=actor, **values)
    write_audit_event(
        event="field_mission.created",
        actor=actor,
        object_type="field_mission",
        object_id=mission.pk,
        metadata={"project_id": project.pk, "assigned_to": assigned_to.pk},
        request_id=request_id,
    )
    _notify(
        assigned_to,
        title="Nouvelle mission terrain",
        body=f"{mission.title} · {project.name}",
        action_url=f"/missions/{mission.pk}",
        dedupe_key=f"mission-created-{mission.pk}",
    )
    return mission


def _transition(mission: FieldMission, *, target: str, allowed: set[str]) -> None:
    if mission.status not in allowed:
        raise ValidationError({"status": "Cette transition n’est pas autorisée pour l’état actuel de la mission."})
    mission.status = target


@transaction.atomic
def accept_mission(mission: FieldMission, *, actor: Any, request_id: str = "") -> FieldMission:
    """L'agent accepte explicitement une mission planifiée."""
    _transition(mission, target=MissionStatus.ACCEPTED, allowed={MissionStatus.PLANNED})
    mission.save(update_fields=("status", "updated_at"))
    write_audit_event(
        event="field_mission.accepted",
        actor=actor,
        object_type="field_mission",
        object_id=mission.pk,
        request_id=request_id,
    )
    _notify(
        mission.created_by,
        title="Mission acceptée",
        body=f"{_actor_name(actor)} a accepté « {mission.title} ».",
        action_url=MANAGER_DASHBOARD_URL,
        dedupe_key=f"mission-accepted-{mission.pk}",
    )
    return mission


@transaction.atomic
def start_mission(
    mission: FieldMission,
    *,
    actor: Any,
    latitude: Any = None,
    longitude: Any = None,
    request_id: str = "",
) -> FieldMission:
    """Démarre une mission ; la position n'est collectée qu'à cet instant si requise."""
    _transition(
        mission,
        target=MissionStatus.IN_PROGRESS,
        allowed={MissionStatus.ACCEPTED, MissionStatus.REVISION_REQUIRED},
    )
    if mission.requires_geo_confirmation and (latitude is None or longitude is None):
        raise ValidationError({"location": "La confirmation de position est requise pour cette mission."})
    mission.started_at = mission.started_at or timezone.now()
    if latitude is not None and longitude is not None:
        mission.start_latitude = latitude
        mission.start_longitude = longitude
        mission.location_confirmed_at = timezone.now()
    mission.last_sync_at = timezone.now()
    mission.save(
        update_fields=(
            "status",
            "started_at",
            "start_latitude",
            "start_longitude",
            "location_confirmed_at",
            "last_sync_at",
            "updated_at",
        )
    )
    write_audit_event(
        event="field_mission.started",
        actor=actor,
        object_type="field_mission",
        object_id=mission.pk,
        metadata={"geo_confirmed": mission.location_confirmed_at is not None},
        request_id=request_id,
    )
    _notify(
        mission.created_by,
        title="Mission en cours",
        body=f"{_actor_name(actor)} a démarré « {mission.title} ».",
        action_url=MANAGER_DASHBOARD_URL,
        dedupe_key=f"mission-started-{mission.pk}",
    )
    return mission


@transaction.atomic
def submit_field_report(report: FieldReport, *, actor: Any, request_id: str = "") -> FieldReport:
    """Soumet un rapport agent et fait entrer la mission dans la file de revue."""
    mission = FieldMission.objects.select_for_update().get(pk=report.mission_id)
    if mission.assigned_to_id != actor.pk:
        raise ValidationError({"mission": "Seul l’agent affecté peut soumettre ce rapport."})
    _transition(
        mission,
        target=MissionStatus.SUBMITTED,
        allowed={MissionStatus.IN_PROGRESS, MissionStatus.REVISION_REQUIRED},
    )
    if not report.summary.strip():
        raise ValidationError({"summary": "Un résumé de visite est requis avant l’envoi."})
    results = {str(item.get("id")): item for item in report.checklist_results if isinstance(item, dict)}
    missing_required = [
        str(item.get("label", item.get("id", "Point de checklist")))
        for item in mission.checklist
        if isinstance(item, dict)
        and item.get("required", False)
        and not bool(results.get(str(item.get("id")), {}).get("completed"))
    ]
    if missing_required:
        raise ValidationError({"checklist_results": f"Complétez les points obligatoires : {', '.join(missing_required[:3])}."})
    report.status = FieldReportStatus.SUBMITTED
    report.submitted_at = timezone.now()
    report.review_comment = ""
    report.save(update_fields=("status", "submitted_at", "review_comment", "updated_at"))
    mission.completed_at = timezone.now()
    mission.last_sync_at = timezone.now()
    mission.save(update_fields=("status", "completed_at", "last_sync_at", "updated_at"))
    write_audit_event(
        event="field_report.submitted",
        actor=actor,
        object_type="field_report",
        object_id=report.pk,
        metadata={"mission_id": mission.pk, "project_id": mission.project_id},
        request_id=request_id,
    )
    _notify(
        mission.created_by,
        title="Nouveau rapport terrain",
        body=f"{_actor_name(actor)} a envoyé le rapport « {mission.title} ».",
        action_url=MANAGER_DASHBOARD_URL,
        dedupe_key=f"field-report-submitted-{report.pk}-{report.submitted_at.isoformat()}",
    )
    return report


@transaction.atomic
def start_report_review(report: FieldReport, *, actor: Any, request_id: str = "") -> FieldReport:
    """Place un rapport soumis en cours de revue chef de projet."""
    mission = FieldMission.objects.select_for_update().get(pk=report.mission_id)
    if report.status != FieldReportStatus.SUBMITTED or mission.status != MissionStatus.SUBMITTED:
        raise ValidationError({"status": "Seul un rapport soumis peut être pris en revue."})
    report.status = FieldReportStatus.UNDER_REVIEW
    report.reviewed_by = actor
    report.reviewed_at = timezone.now()
    report.save(update_fields=("status", "reviewed_by", "reviewed_at", "updated_at"))
    mission.status = MissionStatus.UNDER_REVIEW
    mission.save(update_fields=("status", "updated_at"))
    write_audit_event(
        event="field_report.review_started",
        actor=actor,
        object_type="field_report",
        object_id=report.pk,
        request_id=request_id,
    )
    return report


@transaction.atomic
def approve_field_report(report: FieldReport, *, actor: Any, request_id: str = "") -> FieldReport:
    """Valide un rapport. L'agent auteur ne peut jamais appeler cette transition."""
    mission = FieldMission.objects.select_for_update().get(pk=report.mission_id)
    if report.status not in {FieldReportStatus.SUBMITTED, FieldReportStatus.UNDER_REVIEW}:
        raise ValidationError({"status": "Ce rapport n’est pas prêt à être validé."})
    report.status = FieldReportStatus.APPROVED
    report.reviewed_by = actor
    report.reviewed_at = timezone.now()
    report.review_comment = ""
    report.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"))
    mission.status = MissionStatus.APPROVED
    mission.save(update_fields=("status", "updated_at"))
    write_audit_event(
        event="field_report.approved",
        actor=actor,
        object_type="field_report",
        object_id=report.pk,
        metadata={"mission_id": mission.pk},
        request_id=request_id,
    )
    _notify(
        mission.assigned_to,
        title="Rapport validé",
        body=f"Votre rapport « {mission.title} » a été validé par {_actor_name(actor)}.",
        action_url=f"/missions/{mission.pk}",
        dedupe_key=f"field-report-approved-{report.pk}-{report.reviewed_at.isoformat()}",
    )
    return report


@transaction.atomic
def request_report_revision(
    report: FieldReport,
    *,
    actor: Any,
    reason: str,
    request_id: str = "",
) -> FieldReport:
    """Demande une correction ciblée à l'agent sans recréer la mission."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"reason": "Indiquez le motif de correction (au moins 5 caractères)."})
    mission = FieldMission.objects.select_for_update().get(pk=report.mission_id)
    if report.status not in {FieldReportStatus.SUBMITTED, FieldReportStatus.UNDER_REVIEW}:
        raise ValidationError({"status": "Ce rapport ne peut pas faire l’objet d’une correction."})
    report.status = FieldReportStatus.REVISION_REQUIRED
    report.reviewed_by = actor
    report.reviewed_at = timezone.now()
    report.review_comment = reason
    report.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"))
    mission.status = MissionStatus.REVISION_REQUIRED
    mission.revision_reason = reason
    mission.save(update_fields=("status", "revision_reason", "updated_at"))
    write_audit_event(
        event="field_report.revision_requested",
        actor=actor,
        object_type="field_report",
        object_id=report.pk,
        metadata={"mission_id": mission.pk, "reason": reason},
        request_id=request_id,
    )
    _notify(
        mission.assigned_to,
        title="Correction demandée sur votre rapport",
        body=reason,
        action_url=f"/missions/{mission.pk}",
        dedupe_key=f"field-report-revision-{report.pk}-{report.reviewed_at.isoformat()}",
    )
    return report
