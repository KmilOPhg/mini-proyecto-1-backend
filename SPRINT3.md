# Sprint 3 — Carga diaria y reprogramación inteligente

## Objetivo

Gestionar la **carga horaria planificada por día y usuario** con **límite configurable**, detectar **sobrecarga** sin bloquear al usuario, ofrecer **recomendaciones** (prioridad, vencimiento, duración, tipo) y **reprogramación** en lote o por tarea. La vista **Hoy** refleja cambios al **volver a consultar** tareas y resumen (tras cada mutación).

## Modelo de datos

- **`PerfilCarga`**: `usuario` (OneToOne), `limite_minutos_diario` (default 360, **rango 30–360 min**, tope **6 h**), `advertencia_umbral_pct` (default 85, rango 50–100).
- **`Tarea`** (campos nuevos): `fecha_planificada` (opcional), `duracion_estimada_minutos` (default 60, **15–360 min**), `prioridad` (`BAJA` | `MEDIA` | `ALTA`).
- **Fecha efectiva de plan**: si `fecha_planificada` es nula, se usa la **fecha local** de `fecha_entrega`; si no hay entrega, la de `fecha_creacion`.
- **Ámbito de carga**: solo tareas **raíz** (`parent is null`), **no completadas**.

## Comportamiento

1. **Resumen del día**: suma de `duracion_estimada_minutos` vs `limite_minutos_diario` → `estado_carga`: `ok` | `warning` | `overload`.
2. **Crear/actualizar tarea**: respuesta incluye `resumen_dia` y opcionalmente `carga_alerta` (mensaje no bloqueante).
3. **Recomendaciones**: orden greedy — prioridad baja primero, no-examen antes que examen, más margen de entrega, mayor duración.
4. **Reprogramar**: actualiza `fecha_planificada` de tareas indicadas (solo raíz y del usuario).

## Endpoints (`/tareas/api/...`)

### `GET|PATCH /usuario/carga-config/`

**PATCH** body ejemplo:

```json
{ "limite_minutos_diario": 240 }
```

**GET** respuesta ejemplo:

```json
{
  "limite_minutos_diario": 360,
  "advertencia_umbral_pct": 85,
  "timezone": "server"
}
```

### `GET /dias/{YYYY-MM-DD}/resumen/`

Respuesta ejemplo:

```json
{
  "fecha": "2026-04-15",
  "limite_minutos": 240,
  "advertencia_umbral_pct": 85,
  "total_minutos_planificados": 310,
  "minutos_disponibles": -70,
  "pct_uso": 129.2,
  "estado_carga": "overload",
  "exceso_minutos": 70,
  "tareas": [...]
}
```

### `POST /dias/{fecha}/validar-carga/`

Body:

```json
{
  "cambios": [
    { "tarea_id": 12, "duracion_estimada_minutos": 120, "fecha_planificada": "2026-04-15" },
    { "duracion_estimada_minutos": 90, "fecha_planificada": "2026-04-15" }
  ]
}
```

(`tarea_id` omitido = tarea nueva propuesta.)

### `POST /dias/{fecha}/recomendaciones/`

Body opcional: `{ "ventana_dias": 14, "max_movimientos": 5 }`.

### `POST /dias/{fecha}/reprogramar/`

Body:

```json
{
  "movimientos": [
    { "tarea_id": 15, "nueva_fecha_planificada": "2026-04-17" }
  ]
}
```

## Evidencias (antes / después)

| Antes | Después |
|--------|---------|
| Solo fecha de entrega | Fecha de plan + duración + prioridad para calcular carga |
| Error genérico al “pasarse” de horas | Alertas contextuales + panel de sugerencias + acciones |
| Sin API de ayuda | Validación, recomendaciones y reprogramación documentadas |

## Decisiones técnicas

- **Separar `fecha_entrega` y `fecha_planificada`**: el compromiso con el curso no tiene que ser el día de trabajo.
- **Solo tareas raíz en la carga**: evita doble conteo con subtareas.
- **Heurística greedy v1**: explicable, testeable, sin ML.
- **Actualización en cliente**: refetch de lista + resumen tras reprogramar (tiempo real percibido sin WebSockets en este sprint).
