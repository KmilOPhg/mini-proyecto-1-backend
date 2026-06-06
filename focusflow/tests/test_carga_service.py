from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from focusflow.carga_service import (
    build_resumen,
    estado_carga,
    fecha_efectiva_plan,
    get_or_create_perfil,
    total_minutos_dia,
)
from focusflow.models import PerfilCarga, Tarea


class CargaServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="svcuser", password="Pass12345!")
        self.hoy = date.today()

    def test_get_or_create_perfil(self):
        perfil = get_or_create_perfil(self.user)
        self.assertIsInstance(perfil, PerfilCarga)
        self.assertEqual(perfil.limite_minutos_diario, 360)

        mismo = get_or_create_perfil(self.user)
        self.assertEqual(perfil.pk, mismo.pk)

    def test_fecha_efectiva_plan_prioriza_fecha_planificada(self):
        tarea = Tarea.objects.create(
            nombre="Plan",
            usuario=self.user,
            fecha_planificada=self.hoy + timedelta(days=2),
            fecha_entrega=timezone.now() + timedelta(days=5),
        )
        self.assertEqual(fecha_efectiva_plan(tarea), self.hoy + timedelta(days=2))

    def test_total_minutos_dia_suma_solo_raices_no_completadas(self):
        raiz = Tarea.objects.create(
            nombre="Raíz",
            usuario=self.user,
            fecha_planificada=self.hoy,
            duracion_estimada_minutos=90,
        )
        Tarea.objects.create(
            nombre="Sub",
            usuario=self.user,
            parent=raiz,
            duracion_estimada_minutos=30,
        )
        Tarea.objects.create(
            nombre="Completada",
            usuario=self.user,
            fecha_planificada=self.hoy,
            duracion_estimada_minutos=60,
            completada=True,
        )

        self.assertEqual(total_minutos_dia(self.user, self.hoy), 90)

    def test_estado_carga_overload_warning_ok(self):
        self.assertEqual(estado_carga(400, 360, 85), "overload")
        self.assertEqual(estado_carga(320, 360, 85), "warning")
        self.assertEqual(estado_carga(100, 360, 85), "ok")

    def test_build_resumen_estructura(self):
        Tarea.objects.create(
            nombre="Hoy",
            usuario=self.user,
            fecha_planificada=self.hoy,
            duracion_estimada_minutos=60,
        )

        resumen = build_resumen(self.user, self.hoy)

        self.assertEqual(resumen["fecha"], self.hoy.isoformat())
        self.assertEqual(resumen["total_minutos_planificados"], 60)
        self.assertIn("estado_carga", resumen)
        self.assertEqual(len(resumen["tareas"]), 1)
