from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .base import FocusflowAPITestCase


class RegistroEndpointTests(FocusflowAPITestCase):
    def test_registro_exitoso(self):
        response = self.client.post(
            self.url("/registro/"),
            {
                "username": "nuevo",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "email": "nuevo@example.com",
                "nombre": "Nuevo",
                "apellido": "Usuario",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("mensaje", response.data)
        self.assertTrue(User.objects.filter(username="nuevo").exists())

    def test_registro_passwords_no_coinciden(self):
        response = self.client.post(
            self.url("/registro/"),
            {
                "username": "nuevo2",
                "password": "SecurePass123!",
                "password_confirm": "OtraPass123!",
                "nombre": "Nuevo",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errores", response.data)

    def test_registro_username_duplicado(self):
        User.objects.create_user(username="duplicado", password="SecurePass123!")

        response = self.client.post(
            self.url("/registro/"),
            {
                "username": "duplicado",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "nombre": "Dup",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registro_email_duplicado(self):
        User.objects.create_user(
            username="otro",
            email="dup@example.com",
            password="SecurePass123!",
        )

        response = self.client.post(
            self.url("/registro/"),
            {
                "username": "nuevo3",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "email": "dup@example.com",
                "nombre": "Nuevo",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["errores"])

    def test_registro_usuario_muy_corto(self):
        response = self.client.post(
            self.url("/registro/"),
            {
                "username": "ab",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "nombre": "Nuevo",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data["errores"])

    def test_registro_password_debil(self):
        response = self.client.post(
            self.url("/registro/"),
            {
                "username": "nuevo4",
                "password": "12345678",
                "password_confirm": "12345678",
                "email": "nuevo4@example.com",
                "nombre": "Nuevo",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data["errores"])


class LoginEndpointTests(FocusflowAPITestCase):
    def test_login_exitoso(self):
        response = self.client.post(
            self.url("/login/"),
            {"username": "testuser", "password": "TestPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["nombre_mostrar"], "Test User")

    def test_login_credenciales_invalidas(self):
        response = self.client.post(
            self.url("/login/"),
            {"username": "testuser", "password": "mal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TokenRefreshEndpointTests(FocusflowAPITestCase):
    def test_refresh_token_exitoso(self):
        refresh = RefreshToken.for_user(self.user)

        response = self.client.post(
            self.url("/token/refresh/"),
            {"refresh": str(refresh)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
