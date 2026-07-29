import pymysql
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reset total database (drop & create ulang) lalu migrate dan seed admin — setara 'migrate:fresh --seed' di Laravel"

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-seed',
            action='store_true',
            help='Lewati pembuatan akun admin & konfigurasi default setelah migrasi',
        )

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        name = db['NAME']
        host = db['HOST'] or '127.0.0.1'
        port = int(db['PORT'] or 3306)
        user = db['USER']
        password = db['PASSWORD']

        self.stdout.write(self.style.WARNING(f"[RESET] Menghapus & membuat ulang database '{name}' ..."))

        conn = pymysql.connect(host=host, port=port, user=user, password=password)
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{name}`")
                cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
        finally:
            conn.close()

        self.stdout.write(self.style.SUCCESS("[OK] Database berhasil di-reset."))

        self.stdout.write(self.style.WARNING("[MIGRATE] Menjalankan migrasi ..."))
        call_command('migrate')

        if not options['no_seed']:
            self.stdout.write(self.style.WARNING("[SEED] Membuat akun admin & konfigurasi default ..."))
            call_command('seed_admin')

        self.stdout.write(self.style.SUCCESS("[SELESAI] Instalasi ulang selesai. Login dengan admin / admin123"))
