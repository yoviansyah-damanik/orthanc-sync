import os
from django.db import connection, OperationalError, ProgrammingError
from django.http import HttpResponse, JsonResponse
from django.conf import settings

class MigrationCheckMiddleware:
    """
    Middleware 'Zero-DB Fallback'.
    Memastikan aplikasi tidak crash jika database hilang atau belum termigrasi.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Bypass untuk statis & media
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)

        # 2. Handle API khusus untuk inisialisasi database
        if request.path in ['/api/setup-database', '/api/check-db', '/api/test-db']:
            try:
                from .utils import execute_database_setup, test_db_connection, scan_local_database_ports
                import json

                # Jalankan helper terisolasi untuk setup
                if request.path == '/api/setup-database' and request.method == "POST":
                    data = json.loads(request.body)
                    from .utils import update_env_file
                    env_updates = {
                        'DB_HOST': data.get('host', '127.0.0.1'),
                        'DB_PORT': data.get('port', '3306'),
                        'DB_USER': data.get('user', 'root'),
                        'DB_PASSWORD': data.get('password', ''),
                        'DB_NAME': data.get('db_name', 'orthanc_sync')
                    }
                    # Simpan ke .env dan Update Environment Process Saat Ini
                    from .utils import update_env_file
                    update_env_file(env_updates)
                    
                    # Eksekusi Setup
                    success, message = execute_database_setup(
                        host=data.get('host'),
                        port=data.get('port'),
                        user=data.get('user'),
                        password=data.get('password'),
                        db_name=data.get('db_name')
                    )
                    
                    if success:
                        # PAKSA Update Settings Django di Memory
                        from django.conf import settings as django_settings
                        from django.db import connections
                        
                        # Update dictionary settings
                        new_db_conf = django_settings.DATABASES['default'].copy()
                        new_db_conf.update({
                            'NAME': data.get('db_name'),
                            'USER': data.get('user'),
                            'PASSWORD': data.get('password'),
                            'HOST': data.get('host'),
                            'PORT': str(data.get('port')),
                        })
                        django_settings.DATABASES['default'] = new_db_conf
                        
                        # Update koneksi aktif agar tidak lagi menggunakan placeholder 'mysql'
                        connections['default'].settings_dict.update(new_db_conf)
                        # Tutup koneksi lama agar koneksi baru menggunakan settings baru
                        connections['default'].close()
                    
                    return JsonResponse({"success": success, "message": message})
                
                # Jalankan helper terisolasi untuk test-db
                if request.path == '/api/test-db' and request.method == "POST":
                    data = json.loads(request.body)
                    success, message = test_db_connection(
                        host=data.get('host'),
                        port=data.get('port'),
                        user=data.get('user'),
                        password=data.get('password'),
                        db_name=data.get('db_name')
                    )
                    return JsonResponse({"success": success, "message": message})

                # Untuk check-db, kita kembalikan status dasar secara manual agar aman dari middleware lain
                if request.path == '/api/check-db':
                    db_conf = settings.DATABASES['default']
                    return JsonResponse({
                        "engine": db_conf['ENGINE'].split('.')[-1],
                        "host": db_conf.get('HOST', 'localhost'),
                        "port": db_conf.get('PORT', ''),
                        "can_connect": False, # Status real akan dicek di frontend via test-db
                        "available_services": scan_local_database_ports()
                    })

                return self.get_response(request)
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Setup Error: {str(e)}"})

        # 3. Health Check Database & Dynamic Settings Refresh
        db_ready = False
        try:
            # Muat ulang .env secara manual untuk memastikan kita sinkron dengan file fisik
            env_path = os.path.join(settings.BASE_DIR, '.env')
            db_name_from_env = 'orthanc_sync'
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.startswith('DB_NAME='):
                            db_name_from_env = line.split('=')[1].strip().strip("'").strip('"')
                            break

            current_db = connection.settings_dict.get('NAME')
            
            # Jika sedang menggunakan placeholder atau nama DB tidak sinkron, coba koneksi ulang ke DB asli
            if current_db != db_name_from_env:
                try:
                    # Ambil kredensial terbaru dari environment
                    from .utils import test_db_connection
                    success, _ = test_db_connection(
                        host=os.getenv('DB_HOST', '127.0.0.1'),
                        port=os.getenv('DB_PORT', '3306'),
                        user=os.getenv('DB_USER', 'root'),
                        password=os.getenv('DB_PASSWORD', ''),
                        db_name=db_name_from_env
                    )
                    
                    if success:
                        # Database ternyata sudah ada/siap, update settings di memory
                        from django.db import connections
                        new_conf = settings.DATABASES['default'].copy()
                        new_conf.update({
                            'NAME': db_name_from_env,
                            'USER': os.getenv('DB_USER', 'root'),
                            'PASSWORD': os.getenv('DB_PASSWORD', ''),
                            'HOST': os.getenv('DB_HOST', '127.0.0.1'),
                            'PORT': os.getenv('DB_PORT', '3306'),
                        })
                        settings.DATABASES['default'] = new_conf
                        connection.settings_dict.update(new_conf)
                        connection.close()
                        current_db = db_name_from_env
                except:
                    pass

            if current_db == db_name_from_env:
                # Jika nama sudah sesuai, periksa apakah tabel dasar sudah ada
                with connection.cursor() as cursor:
                    try:
                        # Cek tabel django_migrations sebagai indikator valid
                        cursor.execute("SELECT 1 FROM django_migrations LIMIT 1")
                        db_ready = True
                    except (OperationalError, ProgrammingError):
                        db_ready = False
        except (OperationalError, Exception):
            db_ready = False

        # 4. Jika Database Belum Siap -> Render Setup Page Langsung
        if not db_ready:
            # Baca template secara manual untuk bypass context processors
            template_path = os.path.join(settings.BASE_DIR, 'bridge', 'templates', 'setup_database.html')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    return HttpResponse(f.read())
            
            return HttpResponse(
                "<div style='font-family:sans-serif; text-align:center; margin-top:100px;'>"
                "<h1>Database Belum Terkonfigurasi</h1>"
                "<p>Silakan jalankan migrasi database terlebih dahulu.</p>"
                "</div>"
            )

        # 5. Lanjutkan jika semua OK
        return self.get_response(request)
