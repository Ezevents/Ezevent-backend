# Generated by Django 5.1.4 on 2025-03-12 14:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('promoter', '0002_tickettype_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='profile_pic',
            field=models.CharField(default='https://firebasestorage.googleapis.com/v0/b/happy-hoe.appspot.com/o/dev%2FprofilePic%2F1724404221671_default-user-profile.png?alt=media&token=0793e28f-0230-46ef-abc0-2ea73ebd6fd4', max_length=500, null=True),
        ),
    ]
