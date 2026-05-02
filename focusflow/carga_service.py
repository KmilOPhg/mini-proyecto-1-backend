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

# Mínimo recomendado de actividad diaria: por debajo se considera "subcarga".
MINIMO_RECOMENDADO_MINUTOS = 60


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
    """Tareas raíz no completadas ni pospuestas cuya fecha de plan efectiva coincide con ``day``."""
    qs = Tarea.objects.filter(
        usuario=user,
        parent__isnull=True,
        completada=False,
        pospuesta=False,
    )
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

    qs = Tarea.objects.filter(usuario=user, parent__isnull=True, completada=False, pospuesta=False)
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


# ---------------------------------------------------------------------------
# Análisis integral del día (Sprint 4)
# ---------------------------------------------------------------------------

def _carga_mental_int(t: Tarea) -> int:
    """Convierte ``carga_mental`` (texto 1-5) a entero; 0 si no hay valor válido."""
    try:
        return int(t.carga_mental) if t.carga_mental else 0
    except (TypeError, ValueError):
        return 0


def _due_date(t: Tarea) -> date | None:
    if not t.fecha_entrega:
        return None
    return timezone.localtime(t.fecha_entrega).date()


def _vencida(t: Tarea, day: date) -> bool:
    due = _due_date(t)
    return bool(due and due < day)


def _vence_hoy(t: Tarea, day: date) -> bool:
    due = _due_date(t)
    return bool(due and due == day)


def _vence_pronto(t: Tarea, day: date, dias: int = 2) -> bool:
    """Vence dentro de los próximos ``dias`` días (sin contar hoy)."""
    due = _due_date(t)
    return bool(due and 0 < (due - day).days <= dias)


def _serializar_tarea_analisis(t: Tarea, day: date) -> dict[str, Any]:
    dur = int(t.duracion_estimada_minutos or 0)
    return {
        "id": t.id,
        "nombre": t.nombre,
        "duracion_estimada_minutos": dur,
        "duracion_estimada_horas": round(dur / 60, 2),
        "prioridad": t.prioridad,
        "carga_mental": _carga_mental_int(t),
        "tipo_tarea": t.tipo_tarea,
        "curso": t.curso,
        "fecha_entrega": t.fecha_entrega.isoformat() if t.fecha_entrega else None,
        "fecha_planificada": t.fecha_planificada.isoformat() if t.fecha_planificada else None,
        "vencida": _vencida(t, day),
        "vence_hoy": _vence_hoy(t, day),
        "vence_pronto": _vence_pronto(t, day),
    }


def _nivel_carga(total: int, limite: int, umbral_pct: int) -> str:
    if total <= 0:
        return "vacio"
    if total < MINIMO_RECOMENDADO_MINUTOS:
        return "subcarga"
    if total > limite:
        return "overload"
    if limite > 0 and (100 * total / limite) >= umbral_pct:
        return "warning"
    return "ok"


def _descripcion_nivel(nivel: str, total: int, limite: int) -> str:
    horas = round(total / 60, 1)
    lim_h = round(limite / 60, 1)
    if nivel == "vacio":
        return "Día sin tareas planificadas. Buena oportunidad para adelantar trabajo o descansar."
    if nivel == "subcarga":
        return (
            f"Baja ocupación: solo {horas} h planificadas (mínimo recomendado 1 h). "
            "Considera adelantar tareas pendientes."
        )
    if nivel == "ok":
        return f"Carga adecuada: {horas} h sobre un límite de {lim_h} h."
    if nivel == "warning":
        return f"Cerca del tope: {horas} h de {lim_h} h. Evita sumar tareas largas o de alta carga mental."
    if nivel == "overload":
        exceso_h = round((total - limite) / 60, 1)
        return (
            f"Sobrecarga: {horas} h superan el límite de {lim_h} h en {exceso_h} h. "
            "Conviene reorganizar antes de empezar."
        )
    return ""


def _tareas_pendientes_proximas(user: User, day: date, dias: int) -> list[Tarea]:
    """Tareas raíz (no completadas, no pospuestas) planificadas dentro de los próximos ``dias`` días."""
    qs = Tarea.objects.filter(
        usuario=user,
        parent__isnull=True,
        completada=False,
        pospuesta=False,
    )
    candidatas = []
    for t in qs:
        fp = fecha_efectiva_plan(t)
        if fp <= day:
            continue
        if (fp - day).days <= dias:
            candidatas.append(t)
    return candidatas


def _rec_item(tipo: str, s: dict[str, Any], motivo: str, **extra: Any) -> dict[str, Any]:
    base = {
        "tipo": tipo,
        "tarea_id": s["id"],
        "nombre": s["nombre"],
        "duracion_estimada_minutos": s["duracion_estimada_minutos"],
        "prioridad": s["prioridad"],
        "carga_mental": s["carga_mental"],
        "motivo": motivo,
    }
    base.update(extra)
    return base


def analizar_dia(user: User, day: date, ventana_dias: int = 14) -> dict[str, Any]:
    """Análisis integral del día: nivel de carga + recomendaciones agrupadas por tipo.

    El sistema **solo sugiere**: no modifica ni subdivide tareas. Cada recomendación
    incluye un motivo en lenguaje natural basado en prioridad, carga mental, duración
    estimada y proximidad de la fecha de entrega.
    """
    perfil = get_or_create_perfil(user)
    limite = perfil.limite_minutos_diario

    tareas_objs = list(tareas_raiz_dia(user, day))
    tareas = [_serializar_tarea_analisis(t, day) for t in tareas_objs]
    total = sum(s["duracion_estimada_minutos"] for s in tareas)

    nivel = _nivel_carga(total, limite, perfil.advertencia_umbral_pct)
    descripcion = _descripcion_nivel(nivel, total, limite)
    pct = round(100.0 * total / limite, 1) if limite > 0 else 0.0
    exceso = max(0, total - limite)
    deficit = max(0, MINIMO_RECOMENDADO_MINUTOS - total) if total > 0 else MINIMO_RECOMENDADO_MINUTOS

    alto_impacto_mental = sorted(
        [s for s in tareas if s["carga_mental"] >= 4],
        key=lambda s: (-s["carga_mental"], -s["duracion_estimada_minutos"]),
    )

    recomendaciones: list[dict[str, Any]] = []
    ya_priorizar: set[int] = set()
    ya_cambiar: set[int] = set()
    ya_posponer: set[int] = set()
    ya_reprogramar: set[int] = set()

    # 1) Priorizar — vencidas o vence hoy con prioridad alta.
    for s in tareas:
        if s["vencida"]:
            recomendaciones.append(
                _rec_item(
                    "priorizar",
                    s,
                    "Está vencida; trabajarla primero evita acumular retraso y reduce el costo emocional.",
                )
            )
            ya_priorizar.add(s["id"])
        elif s["vence_hoy"] and s["prioridad"] == "ALTA":
            recomendaciones.append(
                _rec_item(
                    "priorizar",
                    s,
                    "Vence hoy y es prioridad alta: ubícala al inicio del día antes de cualquier otra cosa.",
                )
            )
            ya_priorizar.add(s["id"])

    # 2) Cambiar de horario — alta carga mental y entrega cercana.
    for s in tareas:
        if s["id"] in ya_priorizar:
            continue
        if s["carga_mental"] >= 4 and (s["vence_hoy"] or s["vence_pronto"]):
            recomendaciones.append(
                _rec_item(
                    "cambiar_horario",
                    s,
                    (
                        f"Carga mental {s['carga_mental']}/5 con entrega cercana: prográmala en tu franja "
                        "de mayor concentración (mañana) y separa pausas cortas."
                    ),
                )
            )
            ya_cambiar.add(s["id"])

    # 3 y 4) Solo si hay sobrecarga: posponer y reprogramar a otro día con cupo.
    if nivel == "overload":
        for s in tareas:
            if s["id"] in ya_priorizar or s["id"] in ya_cambiar:
                continue
            if s["prioridad"] == "BAJA" and not s["vencida"] and not s["vence_hoy"]:
                horas_libera = round(s["duracion_estimada_minutos"] / 60, 1)
                recomendaciones.append(
                    _rec_item(
                        "posponer",
                        s,
                        (
                            f"Prioridad baja sin entrega inmediata: pospón para liberar {horas_libera} h "
                            "y bajar la carga total del día."
                        ),
                    )
                )
                ya_posponer.add(s["id"])

        recs_existentes = generar_recomendaciones(
            user, day, ventana_dias=ventana_dias, max_movimientos=5
        )
        for r in recs_existentes["recomendaciones"]:
            tid = r["tarea_id"]
            if tid in ya_posponer or tid in ya_priorizar:
                continue
            s = next((x for x in tareas if x["id"] == tid), None)
            if not s:
                continue
            horas_mov = round(r["duracion_estimada_minutos"] / 60, 1)
            recomendaciones.append(
                _rec_item(
                    "reprogramar",
                    s,
                    (
                        f"Hay cupo el {r['fecha_sugerida']}; mover esta tarea quita {horas_mov} h de hoy. "
                        f"{r['motivo_texto']}"
                    ),
                    fecha_sugerida=r["fecha_sugerida"],
                    impacto_entrega=r["impacto_entrega"],
                )
            )
            ya_reprogramar.add(tid)

    # 5) Subcarga / vacío: sugerir adelantar tareas opcionales sin pasarse del límite.
    sugerencias_opcionales: list[dict[str, Any]] = []
    if nivel in ("vacio", "subcarga"):
        proximas = _tareas_pendientes_proximas(user, day, dias=ventana_dias)
        proximas.sort(
            key=lambda t: (
                -PRIORIDAD_ORDEN.get(t.prioridad, 1),
                _due_date(t) or date.max,
                int(t.duracion_estimada_minutos or 0),
            )
        )
        objetivo = max(MINIMO_RECOMENDADO_MINUTOS, limite // 2) - total
        cupo_restante = max(0, limite - total)
        acumulado = 0
        for t in proximas:
            if acumulado >= objetivo:
                break
            dur = int(t.duracion_estimada_minutos or 0)
            if dur <= 0 or dur > (cupo_restante - acumulado):
                continue
            fp = fecha_efectiva_plan(t)
            sugerencias_opcionales.append(
                {
                    "tipo": "opcional",
                    "tarea_id": t.id,
                    "nombre": t.nombre,
                    "duracion_estimada_minutos": dur,
                    "prioridad": t.prioridad,
                    "carga_mental": _carga_mental_int(t),
                    "fecha_actual": fp.isoformat(),
                    "motivo": (
                        f"Día con baja ocupación: adelantar esta tarea (planificada para {fp.isoformat()}) "
                        f"añade {round(dur / 60, 1)} h sin superar tu límite."
                    ),
                }
            )
            acumulado += dur
        recomendaciones.extend(sugerencias_opcionales)

    return {
        "fecha": day.isoformat(),
        "limite_minutos": limite,
        "limite_horas": round(limite / 60, 2),
        "minimo_recomendado_minutos": MINIMO_RECOMENDADO_MINUTOS,
        "minimo_recomendado_horas": round(MINIMO_RECOMENDADO_MINUTOS / 60, 2),
        "total_minutos": total,
        "total_horas": round(total / 60, 2),
        "minutos_disponibles": max(0, limite - total),
        "exceso_minutos": exceso,
        "deficit_minutos": deficit,
        "pct_uso": pct,
        "nivel_carga": nivel,
        "descripcion_estado": descripcion,
        "tareas": tareas,
        "tareas_alto_impacto_mental": alto_impacto_mental,
        "recomendaciones": recomendaciones,
    }
