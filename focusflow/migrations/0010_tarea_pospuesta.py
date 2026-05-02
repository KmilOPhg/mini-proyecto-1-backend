from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('focusflow', '0009_cap_limite_seis_horas'),
    ]

    operations = [
        # Marca de posposición de una tarea/subtarea
        migrations.AddField(
            model_name='tarea',
            name='pospuesta',
            field=models.BooleanField(
                default=False,
                help_text='True si la tarea está pospuesta y no debe trabajarse ahora.',
            ),
        ),
        # Nota libre del usuario al posponer
        migrations.AddField(
            model_name='tarea',
            name='nota_posponer',
            field=models.CharField(
                blank=True,
                help_text='Nota libre con el motivo o detalle de la posposición (máx. 500 caracteres).',
                max_length=500,
                null=True,
            ),
        ),
        # Auditoría: cuándo se pospuso por última vez
        migrations.AddField(
            model_name='tarea',
            name='pospuesta_en',
            field=models.DateTimeField(
                blank=True,
                help_text='Fecha y hora en la que se pospuso por última vez.',
                null=True,
            ),
        ),
    ]
