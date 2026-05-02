from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from focusflow.serializer import TareaSerializer, RegistroSerializer, FocusflowTokenObtainPairSerializer
from .models import Tarea
from .carga_service import build_resumen, fecha_efectiva_plan
from .swagger_serializers import (
    EliminarTareaResponseSerializer,
    JwtLoginResponseSerializer,
    MensajeErrorSerializer,
    MensajeSimpleSerializer,
    PosponerTareaRequestSerializer,
    PosponerTareaResponseSerializer,
    RegistroOkSerializer,
    TareaCreateResponseSerializer,
)
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone


@extend_schema(
    tags=["Autenticación"],
    summary="Iniciar sesión (JWT)",
    description=(
        "Credenciales **username** / **password**. Respuesta incluye **access**, **refresh** y "
        "**nombre_mostrar** para mostrar en la UI."
    ),
    responses={200: JwtLoginResponseSerializer},
)
class FocusflowTokenObtainPairView(TokenObtainPairView):
    serializer_class = FocusflowTokenObtainPairSerializer


@extend_schema(
    tags=["Autenticación"],
    summary="Renovar token de acceso",
    description="Cuerpo JSON estándar de SimpleJWT con el campo **refresh**.",
)
class FocusflowTokenRefreshView(TokenRefreshView):
    pass

#VISTA LOGIN
class VistaLoginPersonalizada(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        # 0. Verificar si los campos vienen vacíos (validación básica)
        if not username or not password:
            return Response({
                "error_type": "validation",
                "mensaje": "Por favor, completa todos los campos."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 1. Verificar si el usuario existe
        try:
            user_obj = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({
                "error_type": "username",
                "mensaje": f"El usuario '{username}' no está registrado en FocusFlow."
            }, status=status.HTTP_404_NOT_FOUND)

        # 2. Verificar si la contraseña es correcta
        user = authenticate(username=username, password=password)
        if user is None:
            return Response({
                "error_type": "password",
                "mensaje": "La contraseña ingresada es incorrecta."
            }, status=status.HTTP_401_UNAUTHORIZED)

        # 3. Generar tokens si todo está OK
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "mensaje": "Inicio de sesión exitoso"
        }, status=status.HTTP_200_OK)

# VISTA DE REGISTRO
@extend_schema(
    tags=["Autenticación"],
    summary="Registrar nuevo usuario",
    auth=[],
    responses={201: RegistroOkSerializer, 400: MensajeErrorSerializer},
)
class VistaRegistro(generics.CreateAPIView):
    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "mensaje": f"¡Usuario {user.username} creado exitosamente!",
            }, status=status.HTTP_201_CREATED)

        # Si llega aquí, es un 400. Devolvemos los errores específicos de Django.
        return Response({
            "mensaje": "Error en el registro",
            "errores": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

def _payload_carga_tras_tarea(user, tarea):
    if tarea.parent_id:
        return None, None
    day = fecha_efectiva_plan(tarea)
    resumen = build_resumen(user, day)
    alerta = None
    if resumen["estado_carga"] == "overload":
        alerta = {
            "tipo": "overload",
            "mensaje": (
                f"Hoy tienes {resumen['total_minutos_planificados']} min planificados "
                f"y tu límite es {resumen['limite_minutos']} min "
                f"({resumen['exceso_minutos']} min de más)."
            ),
        }
    elif resumen["estado_carga"] == "warning":
        alerta = {
            "tipo": "warning",
            "mensaje": "Estás cerca del límite de carga de hoy; valora repartir o acortar estimaciones.",
        }
    return resumen, alerta


# VISTA TAREAS PROTEGIDA
@extend_schema_view(
    list=extend_schema(
        tags=["Tareas"],
        summary="Listar tareas raíz",
        description=(
            "Devuelve solo tareas **sin padre** del usuario autenticado, cada una con **subtareas** anidadas "
            "(serialización recursiva)."
        ),
    ),
    retrieve=extend_schema(
        tags=["Tareas"],
        summary="Obtener una tarea",
        parameters=[
            OpenApiParameter(
                "id",
                OpenApiTypes.INT,
                OpenApiParameter.PATH,
                required=True,
                description="Identificador de la tarea",
            ),
        ],
    ),
    create=extend_schema(
        tags=["Tareas"],
        summary="Crear tarea",
        description=(
            "`usuario` se asigna automáticamente. Si la tarea es raíz, la respuesta puede incluir "
            "**resumen_dia** y **carga_alerta** según la carga del día planificado."
        ),
        responses={201: TareaCreateResponseSerializer, 400: MensajeErrorSerializer},
    ),
    update=extend_schema(
        tags=["Tareas"],
        summary="Actualizar tarea (PUT)",
        parameters=[
            OpenApiParameter(
                "id",
                OpenApiTypes.INT,
                OpenApiParameter.PATH,
                required=True,
                description="Identificador de la tarea",
            ),
        ],
        responses={200: TareaCreateResponseSerializer, 400: MensajeErrorSerializer},
    ),
    partial_update=extend_schema(
        tags=["Tareas"],
        summary="Actualizar tarea (PATCH)",
        parameters=[
            OpenApiParameter(
                "id",
                OpenApiTypes.INT,
                OpenApiParameter.PATH,
                required=True,
                description="Identificador de la tarea",
            ),
        ],
        responses={200: TareaCreateResponseSerializer, 400: MensajeErrorSerializer},
    ),
    destroy=extend_schema(
        tags=["Tareas"],
        summary="Eliminar tarea",
        description="Elimina la tarea y subtareas en cascada (FK).",
        parameters=[
            OpenApiParameter(
                "id",
                OpenApiTypes.INT,
                OpenApiParameter.PATH,
                required=True,
                description="Identificador de la tarea",
            ),
        ],
        responses={200: EliminarTareaResponseSerializer},
    ),
)
class VistaTarea(viewsets.ModelViewSet):
    serializer_class = TareaSerializer
    permission_classes = [permissions.IsAuthenticated] # Obligatorio estar logueado

    def get_queryset(self):
        # Traemos las que no tienen padre
        # solo devuelve tareas del usuario que hace la petición
        user = self.request.user
        if self.action == 'list':
            return Tarea.objects.filter(usuario=user, parent__isnull=True).prefetch_related('subtareas')
        return Tarea.objects.filter(usuario=user)


    def perform_create(self, serializer):
        # Asigna automáticamente el usuario logueado a la nueva tarea
        serializer.save(usuario=self.request.user)

    # Mensaje al crear una tarea
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            inst = serializer.instance
            resumen, alerta = _payload_carga_tras_tarea(request.user, inst)
            return Response(
                {
                    "mensaje": "¡Tarea creada exitosamente!",
                    "data": serializer.data,
                    "resumen_dia": resumen,
                    "carga_alerta": alerta,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response({
            "mensaje": "Error al validar los datos de la tarea",
            "errores": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    # Mensaje al actualizar una tarea
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False) # Soporta PATCH (actualización parcial)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if serializer.is_valid():
            self.perform_update(serializer)
            inst = serializer.instance
            resumen, alerta = _payload_carga_tras_tarea(request.user, inst)
            return Response(
                {
                    "mensaje": "Tarea actualizada correctamente",
                    "data": serializer.data,
                    "resumen_dia": resumen,
                    "carga_alerta": alerta,
                },
                status=status.HTTP_200_OK,
            )

        return Response({
            "mensaje": "Error en la actualización de la tarea",
            "errores": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    # Mensaje al eliminar una tarea
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        nombre = instance.nombre
        self.perform_destroy(instance)
        return Response({
            "mensaje": f"La tarea '{nombre}' ha sido eliminada con éxito."
        }, status=status.HTTP_200_OK) # Cambiamos a 200 para que el cuerpo del mensaje sea visible

    # Marcar una tarea (raíz o subtarea) como pospuesta con una nota opcional
    @extend_schema(
        tags=["Tareas"],
        summary="Posponer tarea (con nota opcional)",
        description=(
            "Marca la tarea como **pospuesta** y guarda una **nota** libre opcional (máx. 500 caracteres). "
            "No se puede posponer una tarea ya **completada**. Si ya estaba pospuesta, la nota y la "
            "fecha de posposición se sobrescriben."
        ),
        request=PosponerTareaRequestSerializer,
        responses={
            200: PosponerTareaResponseSerializer,
            400: MensajeSimpleSerializer,
            404: MensajeSimpleSerializer,
        },
    )
    @action(detail=True, methods=["post"], url_path="posponer")
    def posponer(self, request, pk=None):
        # La tarea debe pertenecer al usuario autenticado (filtrado en get_queryset)
        instance = self.get_object()

        # No tiene sentido posponer una tarea completada
        if instance.completada:
            return Response(
                {"mensaje": "No se puede posponer una tarea ya completada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validar nota: opcional, máximo 500 caracteres
        nota_raw = request.data.get("nota")
        nota = (nota_raw or "").strip()
        if len(nota) > 500:
            return Response(
                {"mensaje": "La nota no puede tener más de 500 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Persistir la posposición
        instance.pospuesta = True
        instance.nota_posponer = nota or None
        instance.pospuesta_en = timezone.now()
        instance.save(update_fields=["pospuesta", "nota_posponer", "pospuesta_en"])

        serializer = self.get_serializer(instance)
        return Response(
            {"mensaje": "Tarea pospuesta", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    # Quitar el estado pospuesta de la tarea (vuelve al flujo normal)
    @extend_schema(
        tags=["Tareas"],
        summary="Reanudar tarea pospuesta",
        description=(
            "Quita el estado **pospuesta** de la tarea, limpia la **nota** y la marca de tiempo. "
            "La tarea vuelve a aparecer en los flujos normales (por ejemplo `/hoy`)."
        ),
        request=None,
        responses={
            200: PosponerTareaResponseSerializer,
            400: MensajeSimpleSerializer,
            404: MensajeSimpleSerializer,
        },
    )
    @action(detail=True, methods=["post"], url_path="reanudar")
    def reanudar(self, request, pk=None):
        instance = self.get_object()

        # Si nunca estuvo pospuesta, no hacemos nada
        if not instance.pospuesta:
            return Response(
                {"mensaje": "La tarea no estaba pospuesta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Limpiar el estado y los campos asociados
        instance.pospuesta = False
        instance.nota_posponer = None
        instance.pospuesta_en = None
        instance.save(update_fields=["pospuesta", "nota_posponer", "pospuesta_en"])

        serializer = self.get_serializer(instance)
        return Response(
            {"mensaje": "Tarea reanudada", "data": serializer.data},
            status=status.HTTP_200_OK,
        )
