from rest_framework import viewsets, status, generics, permissions
from focusflow.serializer import TareaSerializer, RegistroSerializer, FocusflowTokenObtainPairSerializer
from .models import Tarea
from .carga_service import build_resumen, fecha_efectiva_plan
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.contrib.auth import authenticate


class FocusflowTokenObtainPairView(TokenObtainPairView):
    serializer_class = FocusflowTokenObtainPairSerializer

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
