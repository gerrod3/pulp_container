# Generated by Django 4.2.16 on 2024-10-21 19:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('container', '0041_add_pull_through_pull_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='manifest',
            name='type',
            field=models.CharField(null=True),
        ),
    ]