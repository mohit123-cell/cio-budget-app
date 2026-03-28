from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_sprint4_auth_roles_and_budgeting'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='google_picture_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='join_date',
            field=models.DateField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='profile',
            name='profile_image',
            field=models.FileField(blank=True, null=True, upload_to='profile-images/'),
        ),
        migrations.AddField(
            model_name='profile',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending Approval'), ('active', 'Active'), ('banned', 'Banned')], default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='purchaserequest',
            name='receipt_file',
            field=models.FileField(blank=True, null=True, upload_to='receipts/'),
        ),
        migrations.RunPython(
            lambda apps, schema_editor: apps.get_model('accounts', 'Profile').objects.update(status='active'),
            migrations.RunPython.noop,
        ),
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visibility', models.CharField(choices=[('member', 'Visible to all active members'), ('officer', 'Visible only to officers and treasurers'), ('treasurer', 'Visible only to treasurers')], default='member', max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('is_pinned', models.BooleanField(default=False)),
                ('is_locked', models.BooleanField(default=False)),
                ('attachment', models.FileField(blank=True, null=True, upload_to='announcements/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='announcements', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-is_pinned', '-created_at']},
        ),
        migrations.CreateModel(
            name='ResourceDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visibility', models.CharField(choices=[('member', 'Visible to all active members'), ('officer', 'Visible only to officers and treasurers'), ('treasurer', 'Visible only to treasurers')], default='member', max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('file', models.FileField(upload_to='documents/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_documents', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-uploaded_at']},
        ),
        migrations.CreateModel(
            name='AnnouncementReply',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('announcement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='accounts.announcement')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='announcement_replies', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['created_at']},
        ),
    ]
