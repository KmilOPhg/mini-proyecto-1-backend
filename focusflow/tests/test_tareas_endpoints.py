from datetime import date

from rest_framework import status

from focusflow.models import Tarea

from .base import FocusflowAPITestCase


class TareasAuthTests(FocusflowAPITestCase):
    def test_listar_tareas_requiere_autenticacion(self):
        response = self.client.get(self.url("/tareas/"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TareasCRUDTests(FocusflowAPITestCase):
    def setUp(self):
        super().setUp()
        self.auth_as()

    def test_listar_solo_tareas_raiz_del_usuario(self):
        raiz = self.crear_tarea_raiz(nombre="Raíz")
        self.crear_tarea_raiz(nombre="Sub", parent=raiz)
        self.crear_tarea_raiz(user=self.other_user, nombre="Ajena")

        response = self.client.get(self.url("/tareas/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["nombre"], "Raíz")
        self.assertEqual(len(response.data[0]["subtareas"]), 1)

    def test_crear_tarea_exitosa(self):
        response = self.client.post(
            self.url("/tareas/"),
            self.payload_tarea(nombre="Creada"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("data", response.data)
        self.assertEqual(response.data["data"]["nombre"], "Creada")
        self.assertEqual(Tarea.objects.filter(usuario=self.user).count(), 1)

    def test_crear_tarea_datos_invalidos(self):
        response = self.client.post(
            self.url("/tareas/"),
            self.payload_tarea(duracion_estimada_minutos=5),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errores", response.data)

    def test_obtener_tarea_por_id(self):
        tarea = self.crear_tarea_raiz(nombre="Detalle")

        response = self.client.get(self.url(f"/tareas/{tarea.id}/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nombre"], "Detalle")

    def test_no_puede_ver_tarea_de_otro_usuario(self):
        ajena = self.crear_tarea_raiz(user=self.other_user)

        response = self.client.get(self.url(f"/tareas/{ajena.id}/"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_actualizar_tarea_patch(self):
        tarea = self.crear_tarea_raiz(nombre="Antes")

        response = self.client.patch(
            self.url(f"/tareas/{tarea.id}/"),
            {"nombre": "Después"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["nombre"], "Después")

    def test_eliminar_tarea(self):
        tarea = self.crear_tarea_raiz(nombre="Borrar")

        response = self.client.delete(self.url(f"/tareas/{tarea.id}/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("mensaje", response.data)
        self.assertFalse(Tarea.objects.filter(pk=tarea.id).exists())


class TareasPosponerReanudarTests(FocusflowAPITestCase):
    def setUp(self):
        super().setUp()
        self.auth_as()

    def test_posponer_tarea(self):
        tarea = self.crear_tarea_raiz()

        response = self.client.post(
            self.url(f"/tareas/{tarea.id}/posponer/"),
            {"nota": "Mañana mejor"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tarea.refresh_from_db()
        self.assertTrue(tarea.pospuesta)
        self.assertEqual(tarea.nota_posponer, "Mañana mejor")

    def test_no_posponer_tarea_completada(self):
        tarea = self.crear_tarea_raiz(completada=True)

        response = self.client.post(
            self.url(f"/tareas/{tarea.id}/posponer/"),
            {"nota": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_posponer_nota_demasiado_larga(self):
        tarea = self.crear_tarea_raiz()

        response = self.client.post(
            self.url(f"/tareas/{tarea.id}/posponer/"),
            {"nota": "x" * 501},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reanudar_tarea_pospuesta(self):
        tarea = self.crear_tarea_raiz(pospuesta=True, nota_posponer="pausa")

        response = self.client.post(
            self.url(f"/tareas/{tarea.id}/reanudar/"),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tarea.refresh_from_db()
        self.assertFalse(tarea.pospuesta)
        self.assertIsNone(tarea.nota_posponer)

    def test_reanudar_tarea_no_pospuesta_falla(self):
        tarea = self.crear_tarea_raiz()

        response = self.client.post(
            self.url(f"/tareas/{tarea.id}/reanudar/"),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
