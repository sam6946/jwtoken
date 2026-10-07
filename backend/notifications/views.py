from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from notifications.models import Notification
from notifications.serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user).only(
            "id", "notification_type", "title", "body", "action_url", "data", "read_at", "created_at"
        )
        unread = self.request.query_params.get("unread")
        if unread in {"1", "true", "oui"}:
            queryset = queryset.filter(read_at__isnull=True)
        elif unread in {"0", "false", "non"}:
            queryset = queryset.filter(read_at__isnull=False)
        notification_type = self.request.query_params.get("type")
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        return queryset

    @action(detail=False, methods=("get",), url_path="summary")
    def summary(self, request):
        """Compteur d’en-tête : utile pour la pastille du menu sans charger toute la liste."""
        queryset = Notification.objects.filter(user=request.user).only("id", "read_at")
        return Response({"unread": sum(1 for item in queryset if item.read_at is None), "total": queryset.count()})

    @action(detail=True, methods=("post",), url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=("read_at",))
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=("post",), url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": updated}, status=status.HTTP_200_OK)
