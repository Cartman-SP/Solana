# Generated manually to fix NULL values in total_fees

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mainapp', '0013_admindev_total_tokens'),
    ]

    operations = [
        migrations.RunSQL(
            # SQL для обновления NULL значений в total_fees на 0.0
            sql="""
            UPDATE mainapp_token 
            SET total_fees = 0.0 
            WHERE total_fees IS NULL;
            """,
            # Обратная миграция (не требуется)
            reverse_sql="",
        ),
    ] 