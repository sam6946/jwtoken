from io import BytesIO
import json
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from service_requests.models import ServiceRequest


class ServiceRequestAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media_directory.cleanup()

    def test_public_request_is_saved_with_generated_reference(self):
        response = self.client.post(
            "/api/v1/service-requests/",
            {
                "service_type": "BUILD",
                "first_name": "Awa",
                "last_name": "Fouda",
                "phone": "677 12 34 56",
                "email": "awa@example.com",
                "city": "Douala",
                "project_type": "Villa",
                "description": "Je souhaite construire une maison familiale à Douala.",
                "metadata": {"budget_fcfa": 25000000, "desired_date": "2027-02"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertRegex(response.data["request_code"], r"^KEMTA-REQ-[A-F0-9]{6}$")
        self.assertEqual(response.data["phone"], "+237677123456")
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(ServiceRequest.objects.get().owner, None)

    def test_authenticated_request_is_linked_to_the_owner(self):
        user = User.objects.create_user(
            phone="+237677123461",
            password="KemtA-secure!48271",
            first_name="Mireille",
            last_name="Fopa",
            phone_verified=True,
        )
        self.client.force_authenticate(user=user)
        response = self.client.post(
            "/api/v1/service-requests/",
            {
                "service_type": "MAINTENANCE",
                "first_name": "Mireille",
                "last_name": "Fopa",
                "phone": user.phone,
                "city": "Yaoundé",
                "project_type": "Maison",
                "description": "Inspection périodique de la propriété.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(ServiceRequest.objects.get().owner, user)

    def test_uploads_only_valid_image_documents_and_caps_attachment_count(self):
        image_buffer = BytesIO()
        Image.new("RGB", (32, 32), color=(20, 80, 120)).save(image_buffer, format="PNG")
        image = SimpleUploadedFile("chantier.png", image_buffer.getvalue(), content_type="image/png")
        payload = {
            "service_type": "TAKEOVER",
            "first_name": "Olivier",
            "last_name": "Mba",
            "phone": "+237677123462",
            "city": "Douala",
            "project_type": "Immeuble",
            "description": "Une visite indépendante est nécessaire.",
            "metadata": json.dumps({"progress": "Structure / murs"}),
            "attachments": [image],
        }
        response = self.client.post("/api/v1/service-requests/", payload, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        record = ServiceRequest.objects.get()
        self.assertEqual(record.attachments.count(), 1)
        self.assertEqual(record.attachments.first().original_name, "chantier.png")
