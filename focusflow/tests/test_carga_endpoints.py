from datetime import date, timedelta

from rest_framework import status

from focusflow.models import PerfilCarga

from .base import FocusflowAPITestCase


class CargaConfigEndpointTests(FocusflowAPITestCase):
    def setUp(self):
        super().setUp()
        self.auth_as()

    def test_obtener_config_crea_perfil_si_no_existe(self):
        self.assertFalse(PerfilCarga.objects.filter(usuario=self.user).exists())

        response = self.client.get(self.url("/usuario/carga-config/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["limite_minutos_diario"], 360)
        self.assertTrue(PerfilCarga.objects.filter(usuario=self.user).exists())

    def test_actualizar_config_patch(self):
        response = self.client.patch(
            self.url("/usuario/carga-config/"),
            {"limite_minutos_diario": 180, "advertencia_umbral_pct": 90},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["limite_minutos_diario"], 180)

    def test_actualizar_config_valores_invalidos(self):
        response = self.client.patch(
            self.url("/usuario/carga-config/"),
            {"limite_minutos_diario": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DiaEndpointsTests(FocusflowAPITestCase):
    def setUp(self):
        super().setUp()
        self.auth_as()
        self.hoy = date.today()
        self.fecha_str = self.hoy.isoformat()

    def test_resumen_dia(self):
        self.crear_tarea_raiz(
            nombre="Hoy",
            fecha_planificada=self.hoy,
            duracion_estimada_minutos=60,
        )

        response = self.client.get(self.url(f"/dias/{self.fecha_str}/resumen/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_minutos_planificados"], 60)
        self.assertIn("estado_carga", response.data)

    def test_resumen_fecha_invalida(self):
        response = self.client.get(self.url("/dias/no-es-fecha/resumen/"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validar_carga_dia(self):
        tarea = self.crear_tarea_raiz(fecha_planificada=self.hoy)

        response = self.client.post(
            self.url(f"/dias/{self.fecha_str}/validar-carga/"),
            {
                "cambios": [
                    {
                        "tarea_id": tarea.id,
                        "duracion_estimada_minutos": 120,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_minutos_resultante", response.data)

    def test_validar_carga_cambios_no_es_lista(self):
        response = self.client.post(
            self.url(f"/dias/{self.fecha_str}/validar-carga/"),
            {"cambios": "mal"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_recomendaciones_dia(self):
        self.crear_tarea_raiz(
            fecha_planificada=self.hoy,
            duracion_estimada_minutos=300,
            prioridad="ALTA",
        )

        response = self.client.post(
            self.url(f"/dias/{self.fecha_str}/recomendaciones/"),
            {"ventana_dias": 7, "max_movimientos": 3},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("recomendaciones", response.data)

    def test_analisis_dia(self):
        self.crear_tarea_raiz(fecha_planificada=self.hoy)

        response = self.client.get(
            self.url(f"/dias/{self.fecha_str}/analisis/?ventana_dias=14")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nivel_carga", response.data)
        self.assertIn("recomendaciones", response.data)

    def test_reprogramar_tareas_dia(self):
        tarea = self.crear_tarea_raiz(fecha_planificada=self.hoy)
        manana = (self.hoy + timedelta(days=1)).isoformat()

        response = self.client.post(
            self.url(f"/dias/{self.fecha_str}/reprogramar/"),
            {
                "movimientos": [
                    {"tarea_id": tarea.id, "nueva_fecha_planificada": manana}
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["aplicados"], 1)
        tarea.refresh_from_db()
        self.assertEqual(tarea.fecha_planificada.isoformat(), manana)

    def test_reprogramar_movimientos_vacios(self):
        response = self.client.post(
            self.url(f"/dias/{self.fecha_str}/reprogramar/"),
            {"movimientos": []},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reprogramar_tarea_ajena_retorna_404(self):
        ajena = self.crear_tarea_raiz(user=self.other_user)
        manana = (self.hoy + timedelta(days=1)).isoformat()

        response = self.client.post(
            self.url(f"/dias/{self.fecha_str}/reprogramar/"),
            {
                "movimientos": [
                    {"tarea_id": ajena.id, "nueva_fecha_planificada": manana}
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
