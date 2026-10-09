from io import BytesIO
import logging

from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from projects.models import Evidence

logger = logging.getLogger("kemta")
_VARIANTS = (("thumbnail", 360, 76), ("medium", 960, 80), ("large", 1600, 82))


@shared_task(bind=True, autoretry_for=(OSError, TimeoutError), retry_backoff=True, max_retries=3)
def process_evidence_images(self, evidence_id: int) -> None:
    evidence = Evidence.objects.get(pk=evidence_id)
    if not evidence.image:
        return
    with evidence.image.open("rb") as source:
        original = ImageOps.exif_transpose(Image.open(source))
        if original.mode not in {"RGB", "RGBA"}:
            original = original.convert("RGB")
        elif original.mode == "RGBA":
            background = Image.new("RGB", original.size, (255, 255, 255))
            background.paste(original, mask=original.getchannel("A"))
            original = background
        for field_name, max_width, quality in _VARIANTS:
            variant = original.copy()
            variant.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
            output = BytesIO()
            variant.save(output, format="WEBP", quality=quality, method=5)
            field = getattr(evidence, field_name)
            if field:
                field.delete(save=False)
            field.save(
                f"evidence-{evidence.pk}-{field_name}.webp",
                ContentFile(output.getvalue()),
                save=False,
            )
        evidence.save(update_fields=tuple(field_name for field_name, _, _ in _VARIANTS))
        logger.info("Evidence image variants generated for evidence_id=%s", evidence.pk)
