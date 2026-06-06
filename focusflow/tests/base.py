from datetime import date

from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from focusflow.models import Tarea

API_PREFIX = "/tareas/api"


class FocusflowAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="TestPass123!",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            password="OtherPass123!",
        )
        self.client = APIClient()

    def auth_as(self, user=None):
        user = user or self.user
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def url(self, path: str) -> str:
        return f"{API_PREFIX}{path}"

    def crear_tarea_raiz(self, user=None, **kwargs) -> Tarea:
        user = user or self.user
        defaults = {
            "nombre": "Tarea de prueba",
            "usuario": user,
            "duracion_estimada_minutos": 60,
            "fecha_planificada": date.today(),
            "tipo_tarea": Tarea.TipoTarea.OTRO,
            "prioridad": Tarea.Prioridad.MEDIA,
            "curso": "Curso test",
        }
        defaults.update(kwargs)
        return Tarea.objects.create(**defaults)

    def payload_tarea(self, **overrides) -> dict:
        data = {
            "nombre": "Nueva tarea",
            "duracion_estimada_minutos": 60,
            "fecha_planificada": str(date.today()),
            "tipo_tarea": "OT",
            "prioridad": "MEDIA",
            "curso": "Matemáticas",
        }
        data.update(overrides)
        return data
