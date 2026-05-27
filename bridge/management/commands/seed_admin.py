from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from bridge.models import SystemConfig

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the default admin account and system configurations'

    def handle(self, *args, **kwargs):
        # 1. Seed Admin User
        username = 'admin'
        password = 'admin123'
        email = 'admin@example.com'
        first_name = 'Administrator'

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                password=password,
                email=email,
                first_name=first_name
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created superuser "{username}"'))
        else:
            user = User.objects.get(username=username)
            user.set_password(password)
            user.first_name = first_name
            user.is_superuser = True
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'User "{username}" already exists. Updated password and info.'))

        # 2. Seed System Configurations
        default_configs = [
            {
                'key': 'ORTHANC_URL',
                'value': 'http://localhost:8042',
                'description': 'URL REST API Orthanc PACS'
            },
            {
                'key': 'ORTHANC_USER',
                'value': 'orthanc',
                'description': 'Username untuk autentikasi Orthanc'
            },
            {
                'key': 'ORTHANC_PASS',
                'value': 'orthanc',
                'description': 'Password untuk autentikasi Orthanc'
            },
            {
                'key': 'WORKLIST_DIR',
                'value': 'C:/Orthanc/Worklists',
                'description': 'Direktori tempat menyimpan file .wl (DICOM Worklist)'
            },
        ]

        for cfg in default_configs:
            config, created = SystemConfig.objects.get_or_create(
                key=cfg['key'],
                defaults={'value': cfg['value'], 'description': cfg['description']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created config: {cfg['key']}"))
            else:
                self.stdout.write(self.style.WARNING(f"Config already exists: {cfg['key']}"))
