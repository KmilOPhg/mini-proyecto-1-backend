from datetime import datetime

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .carga_service import (
    aplicar_reprogramaciones,
    build_resumen,
    generar_recomendaciones,
    get_or_create_perfil,
    serializar_tarea_resumen,
    simular_carga,
)
from .models import Tarea
from .serializer import PerfilCargaSerializer


def _parse_fecha(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


class VistaCargaConfig(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        perfil = get_or_create_perfil(request.user)
        return Response(
            {
                "limite_minutos_diario": perfil.limite_minutos_diario,
                "advertencia_umbral_pct": perfil.advertencia_umbral_pct,
                "timezone": str(getattr(request.user, "timezone", "") or "server"),
            }
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


class DiaReprogramarView(APIView):
    permission_classes = [permissions.IsAuthenticated]

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
