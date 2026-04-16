from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from focusflow.models import PerfilCarga, Tarea


class Command(BaseCommand):
    help = (
        "Sembrador: usuario de demostración, PerfilCarga y tareas de ejemplo "
        "(incluye escenario de sobrecarga en «hoy» si el límite es bajo)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            "-u",
            default="demo",
            help="Nombre de usuario a crear o reutilizar (default: demo).",
        )
        parser.add_argument(
            "--password",
            "-p",
            default="demo1234",
            help="Contraseña si el usuario se crea (default: demo1234).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina tareas y perfil de carga de ese usuario antes de sembrar.",
        )
        parser.add_argument(
            "--limite-minutos",
            type=int,
            default=240,
            help="Límite diario en minutos para el perfil (30-360, default 240 = 4 h, útil para ver sobrecarga).",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        reset = options["reset"]
        limite = max(30, min(360, options["limite_minutos"]))

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@example.local",
                "first_name": "Usuario",
                "last_name": "Demo",
            },
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Usuario creado: {username}"))
        else:
            self.stdout.write(self.style.WARNING(f"Usuario existente: {username}"))

        if reset:
            n_tasks, _ = Tarea.objects.filter(usuario=user).delete()
            PerfilCarga.objects.filter(usuario=user).delete()
            self.stdout.write(self.style.WARNING(f"Reset: eliminadas tareas previas del usuario ({n_tasks} filas)."))

        perfil, _ = PerfilCarga.objects.update_or_create(
            usuario=user,
            defaults={
                "limite_minutos_diario": limite,
                "advertencia_umbral_pct": 85,
            },
        )
        self.stdout.write(f"PerfilCarga: límite {perfil.limite_minutos_diario} min/día")

        today = timezone.localdate()
        now = timezone.localtime()

        def dt_today(hour=18, minute=0):
            return timezone.make_aware(
                datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
            )

        def dt_days_ahead(days, hour=23, minute=59):
            d = today + timedelta(days=days)
            return timezone.make_aware(
                datetime.combine(d, datetime.min.time().replace(hour=hour, minute=minute))
            )

        # Evitar duplicar si ya hay tareas raíz (sin --reset)
        if Tarea.objects.filter(usuario=user, parent__isnull=True).exists():
            self.stdout.write(
                self.style.WARNING(
                    "Ya hay tareas raíz para este usuario; omite siembra de tareas. "
                    "Usa --reset para volver a sembrar."
                )
            )
            return

        # Tareas «hoy»: suma 90+75+120 = 285; con límite 240 hay sobrecarga
        t1 = Tarea.objects.create(
            usuario=user,
            nombre="Taller — informe semanal",
            descripcion="Redactar borrador y revisar fuentes",
            completada=False,
            fecha_entrega=dt_today(20, 0),
            fecha_planificada=today,
            carga_mental="3",
            tipo_tarea=Tarea.TipoTarea.TALLER,
            curso="Metodología",
            duracion_estimada_minutos=90,
            prioridad=Tarea.Prioridad.MEDIA,
        )
        t2 = Tarea.objects.create(
            usuario=user,
            nombre="Quiz cap. 4",
            descripcion="Repaso y preguntas tipo examen",
            completada=False,
            fecha_entrega=dt_today(19, 30),
            fecha_planificada=today,
            carga_mental="2",
            tipo_tarea=Tarea.TipoTarea.QUIZ,
            curso="Álgebra",
            duracion_estimada_minutos=75,
            prioridad=Tarea.Prioridad.BAJA,
        )
        t3 = Tarea.objects.create(
            usuario=user,
            nombre="Proyecto — integración",
            descripcion="Unir módulos y pruebas básicas",
            completada=False,
            fecha_entrega=dt_today(22, 0),
            fecha_planificada=today,
            carga_mental="4",
            tipo_tarea=Tarea.TipoTarea.PROYECTO,
            curso="Ingeniería de software",
            duracion_estimada_minutos=120,
            prioridad=Tarea.Prioridad.ALTA,
        )

        Tarea.objects.create(
            usuario=user,
            nombre="Leer capítulo 5",
            descripcion="Notas para la próxima clase",
            completada=False,
            fecha_entrega=dt_days_ahead(3),
            fecha_planificada=today + timedelta(days=1),
            carga_mental="2",
            tipo_tarea=Tarea.TipoTarea.OTRO,
            curso="Literatura",
            duracion_estimada_minutos=60,
            prioridad=Tarea.Prioridad.BAJA,
        )

        Tarea.objects.create(
            usuario=user,
            nombre="Repaso examen final",
            descripcion="Ficha de conceptos clave",
            parent=t1,
        )
        Tarea.objects.create(
            usuario=user,
            nombre="Buscar 3 referencias",
            descripcion="Bibliografía para el taller",
            parent=t1,
        )

        total_hoy = sum(
            Tarea.objects.filter(
                usuario=user, parent__isnull=True, completada=False, fecha_planificada=today
            ).values_list("duracion_estimada_minutos", flat=True)
        )
        self.stdout.write(self.style.SUCCESS(
            f"Sembrado listo: 3 tareas raíz hoy (~{total_hoy} min) + 1 mañana + 2 subtareas bajo «{t1.nombre}»."
        ))
        self.stdout.write(f"Inicia sesión con usuario «{username}» y revisa la vista Hoy.")
