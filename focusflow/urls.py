from django.urls import path, include
from rest_framework import routers
from focusflow import views
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import VistaRegistro, FocusflowTokenObtainPairView

router = routers.DefaultRouter()
router.register(r'tareas', views.VistaTarea, 'tareas')

#Lo que sigue despues de la ruta en config urls
#EJEMPLO: (desde config/urls) /api/tareas
urlpatterns = [
    # Ruta principal para acceder a la app tareas/api/...
    path('api/', include(router.urls)),
    path('api/registro/', VistaRegistro.as_view(), name='registro'),
    path('api/login/', FocusflowTokenObtainPairView.as_view(), name='login'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Ruta para descargar el archivo del esquema (YAML/JSON)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Ruta para ver la interfaz de Swagger en el navegador
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]