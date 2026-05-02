from datetime import datetime

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .carga_service import (
    analizar_dia,
    aplicar_reprogramaciones,
    build_resumen,
    generar_recomendaciones,
    get_or_create_perfil,
    serializar_tarea_resumen,
    simular_carga,
)
from .models import Tarea
from .serializer import PerfilCargaSerializer
from .swagger_serializers import (
    AnalisisDiaResponseSerializer,
    MensajeErrorSerializer,
    MensajeSimpleSerializer,
    PerfilCargaResponseSerializer,
    RecomendacionesRequestSerializer,
    RecomendacionesResponseSerializer,
    ReprogramarRequestSerializer,
    ReprogramarResponseSerializer,
    ResumenDiaSerializer,
    ValidarCargaRequestSerializer,
    ValidarCargaResponseSerializer,
)


def _parse_fecha(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


_FECHA_PARAM = OpenApiParameter(
    name="fecha",
    type=OpenApiTypes.DATE,
    location=OpenApiParameter.PATH,
    required=True,
    description="Día calendario **YYYY-MM-DD** (según configuración `TIME_ZONE` del proyecto).",
)


class VistaCargaConfig(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Carga diaria"],
        summary="Obtener configuración de carga diaria",
        description=(
            "Devuelve el **límite en minutos por día** y el **porcentaje de umbral de aviso**. "
            "Crea `PerfilCarga` si no existe."
        ),
        responses={200: PerfilCargaResponseSerializer},
    )
    def get(self, request):
        perfil = get_or_create_perfil(request.user)
        return Response(
            {
                "limite_minutos_diario": perfil.limite_minutos_diario,
                "advertencia_umbral_pct": perfil.advertencia_umbral_pct,
                "timezone": str(getattr(request.user, "timezone", "") or "server"),
            }
        )

    @extend_schema(
        tags=["Carga diaria"],
        summary="Actualizar configuración de carga diaria",
        description=(
            "Límite entre **30 y 360 minutos** (6 h máx.). Umbral de aviso típico **50–100**."
        ),
        request=PerfilCargaSerializer,
        responses={200: PerfilCargaResponseSerializer, 400: MensajeErrorSerializer},
    )
    def patch(self, request):
        perfil = get_or_create_perfil(request.user)
        ser = PerfilCargaSerializer(perfil, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(
                {"mensaje": "Datos inválidos", "errores": ser.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser.save()
        return Response(
            {
                "limite_minutos_diario": perfil.limite_minutos_diario,
                "advertencia_umbral_pct": perfil.advertencia_umbral_pct,
                "timezone": "server",
            }
        )


class DiaResumenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Carga diaria"],
        summary="Resumen de carga del día",
        description=(
            "Total de minutos planificados para tareas **raíz** no completadas cuya fecha efectiva de plan "
            "coincide con **fecha**; estado **ok / warning / overload**."
        ),
        parameters=[_FECHA_PARAM],
        responses={
            200: ResumenDiaSerializer,
            400: MensajeSimpleSerializer,
        },
    )
    def get(self, request, fecha):
        day = _parse_fecha(fecha)
        if not day:
            return Response(
                {"mensaje": "fecha debe ser YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(build_resumen(request.user, day))


class DiaValidarCargaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Carga diaria"],
        summary="Simular / validar carga del día",
        description=(
            "Lista **cambios** opcionales por `tarea_id` (tarea existente) o sin id para una fila nueva "
            "propuesta (**duracion_estimada_minutos** + **fecha_planificada**)."
        ),
        parameters=[_FECHA_PARAM],
        request=ValidarCargaRequestSerializer,
        responses={
            200: ValidarCargaResponseSerializer,
            400: MensajeSimpleSerializer,
        },
    )
    def post(self, request, fecha):
        day = _parse_fecha(fecha)
        if not day:
            return Response(
                {"mensaje": "fecha debe ser YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cambios = request.data.get("cambios") or []
        if not isinstance(cambios, list):
            return Response(
                {"mensaje": "cambios debe ser un arreglo"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(simular_carga(request.user, day, cambios))


class DiaRecomendacionesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Carga diaria"],
        summary="Generar recomendaciones de reprogramación",
        description=(
            "Heurística por prioridad, tipo (examenes al final), margen de entrega y duración. "
            "**ventana_dias** y **max_movimientos** acotan la búsqueda."
        ),
        parameters=[_FECHA_PARAM],
        request=RecomendacionesRequestSerializer,
        responses={
            200: RecomendacionesResponseSerializer,
            400: MensajeSimpleSerializer,
        },
    )
    def post(self, request, fecha):
        day = _parse_fecha(fecha)
        if not day:
            return Response(
                {"mensaje": "fecha debe ser YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ventana = int(request.data.get("ventana_dias") or 14)
        max_mov = int(request.data.get("max_movimientos") or 5)
        ventana = max(1, min(ventana, 60))
        max_mov = max(1, min(max_mov, 20))
        data = generar_recomendaciones(
            request.user, day, ventana_dias=ventana, max_movimientos=max_mov
        )
        return Response(data)


class DiaAnalisisView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Carga diaria"],
        summary="Análisis integral del día (sin auto-modificar tareas)",
        description=(
            "Devuelve el **nivel de carga** (`vacio | subcarga | ok | warning | overload`), métricas en "
            "horas y minutos, las tareas con **mayor impacto mental** (carga 4-5) y un listado de "
            "**recomendaciones agrupadas** por tipo:\n\n"
            "- `priorizar`: tareas vencidas o con entrega hoy y prioridad alta.\n"
            "- `cambiar_horario`: alta carga mental con entrega cercana (mover a la mejor franja).\n"
            "- `posponer`: solo en sobrecarga, baja prioridad sin entrega inmediata.\n"
            "- `reprogramar`: solo en sobrecarga, mover a otro día con cupo.\n"
            "- `opcional`: en subcarga, adelantar tareas pendientes sin pasar el límite.\n\n"
            "El sistema **no modifica** tareas: cada recomendación incluye un motivo explicativo y el "
            "usuario decide manualmente. Las tareas tampoco se subdividen."
        ),
        parameters=[
            _FECHA_PARAM,
            OpenApiParameter(
                "ventana_dias",
                OpenApiTypes.INT,
                OpenApiParameter.QUERY,
                required=False,
                description="Días hacia adelante a considerar para reprogramar/adelantar (1–60). Por defecto 14.",
            ),
        ],
        responses={
            200: AnalisisDiaResponseSerializer,
            400: MensajeSimpleSerializer,
        },
    )
    def get(self, request, fecha):
        day = _parse_fecha(fecha)
        if not day:
            return Response(
                {"mensaje": "fecha debe ser YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ventana = int(request.query_params.get("ventana_dias") or 14)
        except (TypeError, ValueError):
            ventana = 14
        ventana = max(1, min(ventana, 60))
        return Response(analizar_dia(request.user, day, ventana_dias=ventana))


class DiaReprogramarView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Carga diaria"],
        summary="Aplicar reprogramaciones (fecha planificada)",
        description=(
            "Actualiza **fecha_planificada** de cada tarea raíz indicada. Solo tareas del usuario autenticado."
        ),
        parameters=[_FECHA_PARAM],
        request=ReprogramarRequestSerializer,
        responses={
            200: ReprogramarResponseSerializer,
            400: MensajeSimpleSerializer,
            404: MensajeSimpleSerializer,
        },
    )
    def post(self, request, fecha):
        day = _parse_fecha(fecha)
        if not day:
            return Response(
                {"mensaje": "fecha debe ser YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        movimientos = request.data.get("movimientos")
        if not isinstance(movimientos, list) or not movimientos:
            return Response(
                {"mensaje": "movimientos debe ser un arreglo no vacío"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            actualizadas = aplicar_reprogramaciones(request.user, movimientos)
        except Tarea.DoesNotExist:
            return Response(
                {"mensaje": "Alguna tarea no existe o no te pertenece"},
                status=status.HTTP_404_NOT_FOUND,
            )

        resumen = build_resumen(request.user, day)
        return Response(
            {
                "aplicados": len(actualizadas),
                "resumen_dia": resumen,
                "tareas_actualizadas": [serializar_tarea_resumen(t) for t in actualizadas],
            }
        )
