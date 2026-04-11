from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Tarea
from django.contrib.auth.models import User
import re


class FocusflowTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        full = (user.get_full_name() or "").strip()
        data["nombre_mostrar"] = full if full else user.username
        return data


# Serializador para crear tareas
class TareaSerializer(serializers.ModelSerializer):
    # Esto mostrará la lista de subtareas dentro de cada tarea
    subtareas = serializers.SerializerMethodField()

    class Meta:
        model = Tarea
        fields = '__all__'

    # subtareas = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    def get_subtareas(self, obj):
        # Buscamos las tareas cuyo padre sea la tarea actual
        hijos = Tarea.objects.filter(parent=obj)
        return TareaSerializer(hijos, many=True).data


# Serializador para crear usuarios
class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    nombre = serializers.CharField(write_only=True, max_length=150)
    apellido = serializers.CharField(write_only=True, max_length=150, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'password_confirm', 'email', 'nombre', 'apellido']

    def validate_username(self, value):
        if not re.match(r'^[\w.-]+$', value):
            raise serializers.ValidationError(
                "El nombre de usuario no debe contener espacios ni caracteres especiales."
            )
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Este nombre de usuario ya está en uso.")
        return value

    def validate_nombre(self, value):
        if not (value or "").strip():
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value.strip()

    def validate_apellido(self, value):
        return (value or "").strip()

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Las contraseñas no coinciden.'
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        nombre = validated_data.pop('nombre')
        apellido = validated_data.pop('apellido', '') or ''

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=nombre,
            last_name=apellido,
        )
        return user
