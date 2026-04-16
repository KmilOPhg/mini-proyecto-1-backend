"""
Lógica de carga diaria, sobrecarga y recomendaciones (Sprint 3).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import PerfilCarga, Tarea

PRIORIDAD_ORDEN = {"BAJA": 0, "MEDIA": 1, "ALTA": 2}


def get_or_create_perfil(user: User) -> PerfilCarga:
    perfil, _ = PerfilCarga.objects.get_or_create(
        usuario=user,
        defaults={
            "limite_minutos_diario": 360,
            "advertencia_umbral_pct": 85,
        },
    )
    return perfil


def fecha_efectiva_plan(tarea: Tarea) -> date:
    if tarea.fecha_planificada:
        return tarea.fecha_planificada
    if tarea.fecha_entrega:
        return timezone.localtime(tarea.fecha_entrega).date()
    return timezone.localdate(tarea.fecha_creacion)


def tareas_raiz_dia(user: User, day: date):
    """Tareas de primer nivel no completadas cuya fecha de plan efectiva coincide con day."""
    qs = Tarea.objects.filter(usuario=user, parent__isnull=True, completada=False)
    return [t for t in qs if fecha_efectiva_plan(t) == day]


def total_minutos_dia(user: User, day: date) -> int:
    total = 0
    for t in tareas_raiz_dia(user, day):
        total += int(t.duracion_estimada_minutos or 0)
    return total


def estado_carga(total: int, limite: int, umbral_pct: int) -> str:
    if total > limite:
        return "overload"
    if limite > 0 and (100 * total / limite) >= umbral_pct:
        return "warning"
    return "ok"


def serializar_tarea_resumen(t: Tarea) -> dict[str, Any]:
    return {
        "id": t.id,
        "nombre": t.nombre,
        "duracion_estimada_minutos": t.duracion_estimada_minutos,
        "prioridad": t.prioridad,
        "fecha_entrega": t.fecha_entrega.isoformat() if t.fecha_entrega else None,
        "fecha_planificada": t.fecha_planificada.isoformat() if t.fecha_planificada else None,
        "tipo_tarea": t.tipo_tarea,
        "completada": t.completada,
    }


def build_resumen(user: User, day: date) -> dict[str, Any]:
    perfil = get_or_create_perfil(user)
    limite = perfil.limite_minutos_diario
    total = total_minutos_dia(user, day)
    minutos_disponibles = limite - total
    pct = round(100.0 * total / limite, 1) if limite > 0 else 0.0
    st = estado_carga(total, limite, perfil.advertencia_umbral_pct)
    tareas = [serializar_tarea_resumen(t) for t in tareas_raiz_dia(user, day)]

    exceso = max(0, total - limite)
    return {
        "fecha": day.isoformat(),
        "limite_minutos": limite,
        "advertencia_umbral_pct": perfil.advertencia_umbral_pct,
        "total_minutos_planificados": total,
        "minutos_disponibles": minutos_disponibles,
        "pct_uso": pct,
        "estado_carga": st,
        "exceso_minutos": exceso,
        "tareas": tareas,
    }


def _impacto_entrega(tarea: Tarea, nueva_fecha: date) -> tuple[str, str]:
    if not tarea.fecha_entrega:
        return "bajo", "Sin fecha de entrega definida; reprogramar reduce carga hoy sin compromiso inmediato."
    due = timezone.localtime(tarea.fecha_entrega).date()
    if nueva_fecha > due:
        return "alto", "La nueva fecha queda después del vencimiento; revisa si puedes extender el plazo."
    if (due - nueva_fecha).days <= 2:
        return "medio", "Queda poco margen respecto a la entrega; conviene confirmar fechas."
    return "bajo", "La entrega conserva margen si mueves esta tarea."


def _primer_dia_con_cupo(
    user: User,
    desde: date,
    duracion: int,
    limite: int,
    ventana: int,
    simular_extra_por_dia: dict[date, int] | None = None,
) -> date | None:
    simular_extra_por_dia = simular_extra_por_dia or {}
    for i in range(1, ventana + 1):
        d = desde + timedelta(days=i)
        base = total_minutos_dia(user, d) + simular_extra_por_dia.get(d, 0)
        if base + duracion <= limite:
            return d
    return None


def _sort_key_mover(t: Tarea):
    pri = PRIORIDAD_ORDEN.get(t.prioridad, 1)
    exam_last = 1 if t.tipo_tarea == Tarea.TipoTarea.EXAMEN else 0
    if t.fecha_entrega:
        due_ts = t.fecha_entrega.timestamp()
    else:
        due_ts = float("inf")
    dur = int(t.duracion_estimada_minutos or 0)
    return (pri, exam_last, -due_ts, -dur)


def generar_recomendaciones(
    user: User,
    day: date,
    ventana_dias: int = 14,
    max_movimientos: int = 5,
) -> dict[str, Any]:
    perfil = get_or_create_perfil(user)
    limite = perfil.limite_minutos_diario
    total = total_minutos_dia(user, day)
    exceso = max(0, total - limite)

    candidatos = list(tareas_raiz_dia(user, day))
    candidatos.sort(key=_sort_key_mover)

    recomendaciones: list[dict[str, Any]] = []
    sim_extra: dict[date, int] = {}
    orden = 0

    for t in candidatos:
        if len(recomendaciones) >= max_movimientos:
            break
        if exceso <= 0:
            break
        dur = int(t.duracion_estimada_minutos or 0)
        if dur <= 0:
            continue

        target = _primer_dia_con_cupo(user, day, dur, limite, ventana_dias, sim_extra)
        if target is None:
            continue

        impacto, impacto_txt = _impacto_entrega(t, target)
        pri = t.prioridad
        if pri == "BAJA":
            codigo = "LOW_PRIORITY"
            motivo_texto = "Prioridad baja: suele ser la primera opción para liberar tiempo hoy."
        elif t.tipo_tarea != Tarea.TipoTarea.EXAMEN:
            codigo = "NON_EXAM"
            motivo_texto = "No es examen y suele tener más flexibilidad que evaluaciones."
        else:
            codigo = "EXAM_LAST_RESORT"
            motivo_texto = "Examen: solo se sugiere si otras opciones no bastan para bajar la carga."

        motivo_texto = f"{motivo_texto} {impacto_txt}"

        orden += 1
        score = 1.0 - (orden * 0.05)
        recomendaciones.append(
            {
                "orden": orden,
                "tarea_id": t.id,
                "nombre": t.nombre,
                "duracion_estimada_minutos": dur,
                "accion": "mover_fecha_planificada",
                "fecha_actual": day.isoformat(),
                "fecha_sugerida": target.isoformat(),
                "motivo_codigo": codigo,
                "motivo_texto": motivo_texto,
                "impacto_entrega": impacto,
                "score": round(max(0.5, score), 2),
            }
        )
        sim_extra[target] = sim_extra.get(target, 0) + dur
        exceso -= dur

    total_tras = total
    for r in recomendaciones:
        total_tras -= r["duracion_estimada_minutos"]

    return {
        "fecha": day.isoformat(),
        "exceso_minutos_original": max(0, total - limite),
        "limite_minutos": limite,
        "recomendaciones": recomendaciones,
        "metricas_tras_aplicar_todas": {
            "total_minutos": max(0, total_tras),
            "minutos_disponibles": limite - max(0, total_tras),
            "estado_carga": estado_carga(max(0, total_tras), limite, perfil.advertencia_umbral_pct),
        },
    }


def _parse_day(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return datetime.strptime(val[:10], "%Y-%m-%d").date()
    return None


def simular_carga(
    user: User,
    day: date,
    cambios: list[dict[str, Any]],
) -> dict[str, Any]:
    """cambios: [{ tarea_id?, duracion_estimada_minutos?, fecha_planificada? }]; sin tarea_id = tarea nueva propuesta."""
    perfil = get_or_create_perfil(user)
    limite = perfil.limite_minutos_diario

    overrides: dict[int, tuple[int | None, date | None]] = {}
    extra_nuevo_en_dia = 0
    for ch in cambios:
        tid = ch.get("tarea_id")
        fp = _parse_day(ch.get("fecha_planificada"))
        dur = ch.get("duracion_estimada_minutos")
        if tid is None:
            if fp == day and dur is not None:
                extra_nuevo_en_dia += int(dur)
            continue
        overrides[int(tid)] = (
            dur,
            fp,
        )

    def efectivo_sim(t: Tarea) -> date:
        if t.id in overrides:
            _, fp = overrides[t.id]
            if fp is not None:
                return fp
        return fecha_efectiva_plan(t)

    def dur_sim(t: Tarea) -> int:
        if t.id in overrides:
            d, _ = overrides[t.id]
            if d is not None:
                return int(d)
        return int(t.duracion_estimada_minutos or 0)

    qs = Tarea.objects.filter(usuario=user, parent__isnull=True, completada=False)
    total = extra_nuevo_en_dia
    for t in qs:
        if efectivo_sim(t) == day:
            total += dur_sim(t)

    valido = total <= limite
    exceso = max(0, total - limite)
    return {
        "valido": valido,
        "total_minutos_resultante": total,
        "limite_minutos": limite,
        "exceso_minutos": exceso,
        "mensaje_codigo": "OK" if valido else "DAILY_OVERLOAD",
        "mensaje_usuario": (
            "La carga queda dentro de tu límite diario."
            if valido
            else f"Con estos valores tu día superaría el límite en {exceso} min ({exceso // 60}h {exceso % 60}m)."
        ),
    }


def aplicar_reprogramaciones(user: User, movimientos: list[dict[str, Any]]) -> list[Tarea]:
    """movimientos: [{ tarea_id, nueva_fecha_planificada: 'YYYY-MM-DD' }]"""
    updated: list[Tarea] = []
    with transaction.atomic():
        for m in movimientos:
            tid = m.get("tarea_id")
            raw = m.get("nueva_fecha_planificada")
            if tid is None or not raw:
                continue
            if isinstance(raw, str):
                nueva = datetime.strptime(raw, "%Y-%m-%d").date()
            else:
                nueva = raw
            tarea = Tarea.objects.select_for_update().get(pk=tid, usuario=user, parent__isnull=True)
            tarea.fecha_planificada = nueva
            tarea.save(update_fields=["fecha_planificada"])
            updated.append(tarea)
    return updated


def resumen_tras_movimientos(user: User, day: date, tareas_afectadas: list[Tarea]) -> dict[str, Any]:
    base = build_resumen(user, day)
    base["tareas_actualizadas"] = [serializar_tarea_resumen(t) for t in tareas_afectadas]
    return base
