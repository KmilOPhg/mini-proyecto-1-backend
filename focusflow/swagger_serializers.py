"""
Serializadores usados solo para documentación OpenAPI (Swagger / drf-spectacular).
No sustituyen la validación en tiempo de ejecución de las APIView que usan dict/json libre.
"""

from rest_framework import serializers


class CambioSimulacionSerializer(serializers.Serializer):
    """Ítem dentro de `cambios` en validar-carga."""

    tarea_id = serializers.IntegerField(required=False, allow_null=True)
    duracion_estimada_minutos = serializers.IntegerField(required=False)
    fecha_planificada = serializers.DateField(required=False)


class ValidarCargaRequestSerializer(serializers.Serializer):
    cambios = CambioSimulacionSerializer(many=True)


class RecomendacionesRequestSerializer(serializers.Serializer):
    ventana_dias = serializers.IntegerField(required=False, default=14, min_value=1, max_value=60)
    max_movimientos = serializers.IntegerField(required=False, default=5, min_value=1, max_value=20)


class MovimientoReprogramarSerializer(serializers.Serializer):
    tarea_id = serializers.IntegerField()
    nueva_fecha_planificada = serializers.DateField()


class ReprogramarRequestSerializer(serializers.Serializer):
    movimientos = MovimientoReprogramarSerializer(many=True)


class PerfilCargaResponseSerializer(serializers.Serializer):
    limite_minutos_diario = serializers.IntegerField()
    advertencia_umbral_pct = serializers.IntegerField()
    timezone = serializers.CharField()


class CargaAlertaSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    mensaje = serializers.CharField()


class TareaCreateResponseSerializer(serializers.Serializer):
    mensaje = serializers.CharField()
    data = serializers.DictField()
    resumen_dia = serializers.DictField(allow_null=True)
    carga_alerta = CargaAlertaSerializer(allow_null=True)


class MensajeErrorSerializer(serializers.Serializer):
    mensaje = serializers.CharField()
    errores = serializers.DictField(required=False)


class TareaResumenItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    duracion_estimada_minutos = serializers.IntegerField()
    prioridad = serializers.CharField()
    fecha_entrega = serializers.CharField(allow_null=True)
    fecha_planificada = serializers.CharField(allow_null=True)
    tipo_tarea = serializers.CharField()
    completada = serializers.BooleanField()


class ResumenDiaSerializer(serializers.Serializer):
    fecha = serializers.CharField(help_text="YYYY-MM-DD")
    limite_minutos = serializers.IntegerField()
    advertencia_umbral_pct = serializers.IntegerField()
    total_minutos_planificados = serializers.IntegerField()
    minutos_disponibles = serializers.IntegerField()
    pct_uso = serializers.FloatField()
    estado_carga = serializers.CharField(help_text="ok | warning | overload")
    exceso_minutos = serializers.IntegerField()
    tareas = TareaResumenItemSerializer(many=True)


class ValidarCargaResponseSerializer(serializers.Serializer):
    valido = serializers.BooleanField()
    total_minutos_resultante = serializers.IntegerField()
    limite_minutos = serializers.IntegerField()
    exceso_minutos = serializers.IntegerField()
    mensaje_codigo = serializers.CharField()
    mensaje_usuario = serializers.CharField()


class ReprogramarResponseSerializer(serializers.Serializer):
    aplicados = serializers.IntegerField()
    resumen_dia = ResumenDiaSerializer()
    tareas_actualizadas = TareaResumenItemSerializer(many=True)


class ItemRecomendacionSerializer(serializers.Serializer):
    orden = serializers.IntegerField()
    tarea_id = serializers.IntegerField()
    nombre = serializers.CharField()
    duracion_estimada_minutos = serializers.IntegerField()
    accion = serializers.CharField()
    fecha_actual = serializers.CharField()
    fecha_sugerida = serializers.CharField()
    motivo_codigo = serializers.CharField()
    motivo_texto = serializers.CharField()
    impacto_entrega = serializers.CharField()
    score = serializers.FloatField()


class MetricasTrasAplicarSerializer(serializers.Serializer):
    total_minutos = serializers.IntegerField()
    minutos_disponibles = serializers.IntegerField()
    estado_carga = serializers.CharField()


class RecomendacionesResponseSerializer(serializers.Serializer):
    fecha = serializers.CharField()
    exceso_minutos_original = serializers.IntegerField()
    limite_minutos = serializers.IntegerField()
    recomendaciones = ItemRecomendacionSerializer(many=True)
    metricas_tras_aplicar_todas = MetricasTrasAplicarSerializer()


class JwtLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    nombre_mostrar = serializers.CharField()


class RegistroOkSerializer(serializers.Serializer):
    mensaje = serializers.CharField()


class EliminarTareaResponseSerializer(serializers.Serializer):
    mensaje = serializers.CharField()


class MensajeSimpleSerializer(serializers.Serializer):
    mensaje = serializers.CharField()


class PosponerTareaRequestSerializer(serializers.Serializer):
    """Cuerpo aceptado por POST /api/tareas/<id>/posponer/."""

    nota = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Texto libre con el motivo o detalle de la posposición (opcional, máx. 500 caracteres).",
    )


class PosponerTareaResponseSerializer(serializers.Serializer):
    """Respuesta de posponer / reanudar una tarea."""

    mensaje = serializers.CharField()
    data = serializers.DictField()


class TareaAnalisisItemSerializer(serializers.Serializer):
    """Tarea enriquecida con flags usados por el análisis del día."""

    id = serializers.IntegerField()
    nombre = serializers.CharField()
    duracion_estimada_minutos = serializers.IntegerField()
    duracion_estimada_horas = serializers.FloatField()
    prioridad = serializers.CharField()
    carga_mental = serializers.IntegerField(min_value=0, max_value=5)
    tipo_tarea = serializers.CharField()
    curso = serializers.CharField(allow_null=True)
    fecha_entrega = serializers.CharField(allow_null=True)
    fecha_planificada = serializers.CharField(allow_null=True)
    vencida = serializers.BooleanField()
    vence_hoy = serializers.BooleanField()
    vence_pronto = serializers.BooleanField()


class RecomendacionAnalisisSerializer(serializers.Serializer):
    """Cada item de ``recomendaciones`` en el análisis del día."""

    tipo = serializers.ChoiceField(
        choices=["priorizar", "cambiar_horario", "posponer", "reprogramar", "opcional"],
        help_text="Categoría de la recomendación.",
    )
    tarea_id = serializers.IntegerField()
    nombre = serializers.CharField()
    duracion_estimada_minutos = serializers.IntegerField()
    prioridad = serializers.CharField()
    carga_mental = serializers.IntegerField(min_value=0, max_value=5)
    motivo = serializers.CharField(help_text="Explicación breve del motivo.")
    fecha_sugerida = serializers.CharField(required=False, allow_null=True)
    fecha_actual = serializers.CharField(required=False, allow_null=True)
    impacto_entrega = serializers.CharField(required=False, allow_null=True)


class AnalisisDiaResponseSerializer(serializers.Serializer):
    """Respuesta de ``GET /api/dias/<fecha>/analisis/``."""

    fecha = serializers.CharField(help_text="YYYY-MM-DD")
    limite_minutos = serializers.IntegerField()
    limite_horas = serializers.FloatField()
    minimo_recomendado_minutos = serializers.IntegerField()
    minimo_recomendado_horas = serializers.FloatField()
    total_minutos = serializers.IntegerField()
    total_horas = serializers.FloatField()
    minutos_disponibles = serializers.IntegerField()
    exceso_minutos = serializers.IntegerField()
    deficit_minutos = serializers.IntegerField()
    pct_uso = serializers.FloatField()
    nivel_carga = serializers.ChoiceField(
        choices=["vacio", "subcarga", "ok", "warning", "overload"],
    )
    descripcion_estado = serializers.CharField()
    tareas = TareaAnalisisItemSerializer(many=True)
    tareas_alto_impacto_mental = TareaAnalisisItemSerializer(many=True)
    recomendaciones = RecomendacionAnalisisSerializer(many=True)
