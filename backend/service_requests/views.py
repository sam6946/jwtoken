from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils.text import get_valid_filename
from PIL import Image, UnidentifiedImageError
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from common.services import write_audit_event
from service_requests.models import ServiceRequest, ServiceRequestAttachment
from service_requests.permissions import ServiceRequestAccessPermission
from service_requests.serializers import ServiceRequestAdminSerializer, ServiceRequestCreateSerializer

_ALLOWED_FILES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
}
_MAX_ATTACHMENT_COUNT = 5
_MAX_ATTACHMENT_SIZE = 8 * 1024 * 1024
_MAX_TOTAL_ATTACHMENT_SIZE = 32 * 1024 * 1024


def validate_attachment(file_obj: UploadedFile) -> None:
    suffix = Path(file_obj.name).suffix.lower()
    allowed_types = _ALLOWED_FILES.get(suffix)
    if not allowed_types or file_obj.content_type not in allowed_types:
        raise ValidationError({"attachments": "Seuls les fichiers JPG, PNG, WebP et PDF sont autorisés."})
    if file_obj.size <= 0 or file_obj.size > _MAX_ATTACHMENT_SIZE:
        raise ValidationError({"attachments": "Chaque fichier doit faire entre 1 octet et 8 Mo."})
    file_obj.seek(0)
    if suffix == ".pdf":
        signature = file_obj.read(5)
        if signature != b"%PDF-":
            raise ValidationError({"attachments": "Le fichier PDF transmis n’est pas valide."})
    else:
        try:
            with Image.open(file_obj) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError({"attachments": "Une image transmise n’est pas valide."}) from exc
    file_obj.seek(0)


class ServiceRequestViewSet(viewsets.ModelViewSet):
    permission_classes = (ServiceRequestAccessPermission,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "service_request"

    def get_queryset(self):
        user = self.request.user
        queryset = ServiceRequest.objects.select_related("owner").prefetch_related("attachments")
        if user.is_authenticated and (user.is_staff or user.role in {"ADMIN", "SUPER_ADMIN"}):
            return queryset
        if user.is_authenticated:
            return queryset.filter(owner=user)
        return queryset.none()

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return ServiceRequestAdminSerializer
        return ServiceRequestCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachments = request.FILES.getlist("attachments")
        if len(attachments) > _MAX_ATTACHMENT_COUNT:
            raise ValidationError({"attachments": f"Vous pouvez joindre au maximum {_MAX_ATTACHMENT_COUNT} fichiers."})
        if sum(item.size for item in attachments) > _MAX_TOTAL_ATTACHMENT_SIZE:
            raise ValidationError({"attachments": "La taille totale des pièces jointes dépasse 32 Mo."})
        for attachment in attachments:
            validate_attachment(attachment)

        with transaction.atomic():
            owner = request.user if request.user.is_authenticated else None
            service_request = serializer.save(owner=owner)
            for uploaded_file in attachments:
                ServiceRequestAttachment.objects.create(
                    service_request=service_request,
                    file=uploaded_file,
                    original_name=get_valid_filename(uploaded_file.name)[:255],
                    content_type=uploaded_file.content_type or "",
                    file_size=uploaded_file.size,
                )
            write_audit_event(
                event="service_request.created",
                actor=owner,
                object_type="service_request",
                object_id=service_request.pk,
                metadata={
                    "service_type": service_request.service_type,
                    "attachment_count": len(attachments),
                    "related_project_id": service_request.related_project_id,
                },
                request_id=getattr(request, "request_id", ""),
            )
        response_serializer = ServiceRequestCreateSerializer(service_request, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        if not (self.request.user.is_staff or self.request.user.role in {"ADMIN", "SUPER_ADMIN"}):
            raise ValidationError("Seul un administrateur peut modifier une demande.")
        serializer.save()
        write_audit_event(
            event="service_request.updated",
            actor=self.request.user,
            object_type="service_request",
            object_id=serializer.instance.pk,
            request_id=getattr(self.request, "request_id", ""),
        )
