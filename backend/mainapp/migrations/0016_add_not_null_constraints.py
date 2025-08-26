# Generated manually to add NOT NULL constraints

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mainapp', '0015_fix_total_trans_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='token',
            name='total_fees',
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterField(
            model_name='token',
            name='total_trans',
            field=models.IntegerField(default=0),
        ),
    ] 