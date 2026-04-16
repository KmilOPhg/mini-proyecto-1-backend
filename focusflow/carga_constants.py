"""Límites de carga diaria (Sprint 3) — única fuente de verdad para validaciones."""

# Límite configurable por usuario: entre 30 min y 6 h como máximo.
LIMITE_DIARIO_MIN_MINUTOS = 30
LIMITE_DIARIO_MAX_MINUTOS = 360

# Una tarea no puede tener más duración estimada que el tope diario máximo.
DURACION_TAREA_MIN_MINUTOS = 15
DURACION_TAREA_MAX_MINUTOS = LIMITE_DIARIO_MAX_MINUTOS
