from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

from .carga_constants import (
    DURACION_TAREA_MAX_MINUTOS,
    DURACION_TAREA_MIN_MINUTOS,
    LIMITE_DIARIO_MAX_MINUTOS,
    LIMITE_DIARIO_MIN_MINUTOS,
)


class PerfilCarga(models.Model):
    """Límite diario configurable por usuario (Sprint 3)."""

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil_carga",
    )
    limite_minutos_diario = models.PositiveIntegerField(
        default=360,
        validators=[
            MinValueValidator(LIMITE_DIARIO_MIN_MINUTOS),
            MaxValueValidator(LIMITE_DIARIO_MAX_MINUTOS),
        ],
        help_text="Carga máxima planificable por día (30–360 min; máximo 6 h).",
    )
    advertencia_umbral_pct = models.PositiveSmallIntegerField(
        default=85,
        help_text="Porcentaje del límite a partir del cual se muestra aviso (no bloqueante).",
    )

    class Meta:
        verbose_name = "Perfil de carga"
        verbose_name_plural = "Perfiles de carga"

    def __str__(self):
        return f"Carga {self.usuario.username}: {self.limite_minutos_diario} min/día"


class Tarea(models.Model):
    # 1. Definimos las opciones del Enum aquí dentro
    class TipoTarea(models.TextChoices):
        EXAMEN = 'EX', 'Examen'
        QUIZ = 'QU', 'Quiz'
        TALLER = 'TA', 'Taller'
        PROYECTO = 'PR', 'Proyecto'
        OTRO = 'OT', 'Otro'

    class Prioridad(models.TextChoices):
        BAJA = 'BAJA', 'Baja'
        MEDIA = 'MEDIA', 'Media'
        ALTA = 'ALTA', 'Alta'

    nombre = models.CharField(max_length=100, help_text="El nombre descriptivo de la tarea")
    descripcion = models.CharField(max_length=100, null=True, blank=True, help_text="La descripción de la tarea")
    completada = models.BooleanField(default=False, help_text="Casilla para marcar la tarea como completa")
    fecha_entrega = models.DateTimeField(null=True, blank=True, help_text="Formato: AAAA-MM-DD HH:MM:SS")
    fecha_creacion = models.DateTimeField(default=timezone.now, help_text="Fecha de creacion de la tarea")
    carga_mental = models.CharField(null=True, blank=True, max_length=100, help_text="Carga mental (1-5)")

    #Así se define el campo tipo_tarea
    tipo_tarea = models.CharField(
        max_length=2,
        choices=TipoTarea.choices,
        default=TipoTarea.OTRO,
        help_text="Selecciona el tipo de tarea"
    )

    curso = models.CharField(default="Sin definir",  max_length=255, help_text="Casilla para el curso")

    fecha_planificada = models.DateField(
        null=True,
        blank=True,
        help_text="Día en que planeas trabajar esta tarea (si vacío, se usa la fecha de entrega).",
    )
    duracion_estimada_minutos = models.PositiveIntegerField(
        default=60,
        validators=[
            MinValueValidator(DURACION_TAREA_MIN_MINUTOS),
            MaxValueValidator(DURACION_TAREA_MAX_MINUTOS),
        ],
        help_text="Tiempo estimado de trabajo en minutos (15–360; no más que 6 h).",
    )
    prioridad = models.CharField(
        max_length=8,
        choices=Prioridad.choices,
        default=Prioridad.MEDIA,
    )

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtareas',
        help_text="ID de la tarea padre"
    )

    # Relacionamos la tarea con un usuario
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tareas',
        null=True, # Migrar si ya hay datos
        blank=True
    )

    def save(self, *args, **kwargs):
        # Herencia lógica de la tarea padre a la subtarea
        if self.parent:
            # Heredar fecha de entrega si la subtarea no tiene una propia
            if not self.fecha_entrega:
                self.fecha_entrega = self.parent.fecha_entrega

            # Heredar carga mental
            if not self.carga_mental:
                self.carga_mental = self.parent.carga_mental

            # Heredar el TIPO DE TAREA del Enum
            if not self.tipo_tarea or self.tipo_tarea == self.TipoTarea.OTRO:
                self.tipo_tarea = self.parent.tipo_tarea

            # Descripción automática basada en el padre
            if not self.descripcion:
                self.descripcion = f"Subtarea de: {self.parent.nombre}"

            # Herencia del curso
            if not self.curso:
                self.curso = self.parent.curso

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre
