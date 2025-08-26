# Generated manually to fix NULL values in total_trans

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mainapp', '0014_fix_total_fees_null'),
    ]

    operations = [
        migrations.RunSQL(
            # SQL для обновления NULL значений в total_trans на 0
            sql="""
            UPDATE mainapp_token 
            SET total_trans = 0 
            WHERE total_trans IS NULL;
            """,
            # Обратная миграция (не требуется)
            reverse_sql="",
        ),
    ] 