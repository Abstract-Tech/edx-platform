# Generated by Django 4.2.10 on 2024-02-23 06:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mobile_api', '0004_mobileconfig'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mobileconfig',
            name='value',
            field=models.CharField(max_length=1000),
        ),
    ]
