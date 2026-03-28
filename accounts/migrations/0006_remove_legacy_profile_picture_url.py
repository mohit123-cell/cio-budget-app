from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_full_project_features'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='profile_picture_url',
        ),
    ]
