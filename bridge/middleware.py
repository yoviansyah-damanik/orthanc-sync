import hashlib
import os
import re
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


# ─── Konstanta watermark ───────────────────────────────────────────────────────
_WM_TEMPLATE = os.path.join(str(settings.BASE_DIR), 'bridge', 'templates', 'base.html')
_WM_START = '<!-- WATERMARK_START -->'
_WM_END   = '<!-- WATERMARK_END -->'
_WM_ENV_KEY = 'WATERMARK_HASH'

_LOCKOUT_PAGE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Aplikasi Terkunci</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{min-height:100vh;display:flex;align-items:center;justify-content:center;
         background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);
         font-family:'Segoe UI',sans-serif;color:#fff}
    .card{background:rgba(255,255,255,.05);backdrop-filter:blur(24px);
          border:1px solid rgba(255,255,255,.12);border-radius:24px;
          padding:3rem;text-align:center;max-width:480px;width:90%;
          box-shadow:0 25px 50px rgba(0,0,0,.5)}
    .icon{font-size:4rem;margin-bottom:1.5rem;display:block;
          animation:pulse 2s ease-in-out infinite}
    @keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.1)}}
    h1{font-size:1.5rem;font-weight:800;margin-bottom:.75rem;
       background:linear-gradient(135deg,#f87171,#fbbf24);
       -webkit-background-clip:text;-webkit-text-fill-color:transparent}
    p{font-size:.875rem;color:rgba(255,255,255,.6);line-height:1.75;margin-bottom:1.5rem}
    .badge{display:inline-flex;align-items:center;gap:.5rem;
           background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);
           color:#f87171;font-size:.75rem;font-weight:700;padding:.5rem 1rem;
           border-radius:999px;letter-spacing:.05em;text-transform:uppercase}
  </style>
</head>
<body>
  <div class="card">
    <span class="icon">🔒</span>
    <h1>Lisensi Tidak Valid</h1>
    <p>Integritas aplikasi ini telah dirusak.<br>
       Watermark developer telah dihapus atau dimodifikasi.<br>
       Hubungi developer untuk pemulihan akses.</p>
    <div class="badge">
      <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
      </svg>
      Yoviansyah Rizki Pratama &mdash; 0812-2277-8197
    </div>
  </div>
</body>
</html>"""


def _wm_compute_hash(content: str) -> str:
    """Hitung SHA-256 dari blok watermark (normalized whitespace)."""
    normalized = ' '.join(content.split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def _wm_extract_block(html: str) -> str:
    """Ambil konten antara WATERMARK_START dan WATERMARK_END."""
    start = html.find(_WM_START)
    end   = html.find(_WM_END)
    if start == -1 or end == -1:
        return ''
    return html[start: end + len(_WM_END)]


class WatermarkGuardMiddleware:
    """
    Middleware penjaga watermark.
    Setiap request: baca base.html, hash blok watermark, bandingkan dengan .env.
    Jika tidak cocok → kembalikan halaman lockout 503.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Muat hash referensi dari env saat startup
        self._ref_hash = os.getenv(_WM_ENV_KEY, '')

    def __call__(self, request):
        # Bypass: statis, media, dan endpoint setup
        skip_prefixes = ('/static/', '/media/', '/api/setup-database',
                         '/api/check-db', '/api/test-db')
        if any(request.path.startswith(p) for p in skip_prefixes):
            return self.get_response(request)

        # Lazy-load hash referensi (untuk pickup setelah generate_watermark_hash)
        ref_hash = os.getenv(_WM_ENV_KEY, self._ref_hash)

        # Jika belum ada hash referensi, lewati validasi (mode pertama kali)
        if not ref_hash:
            return self.get_response(request)

        # Baca template fisik
        try:
            with open(_WM_TEMPLATE, 'r', encoding='utf-8') as f:
                html = f.read()
        except OSError:
            # Jika file tidak bisa dibaca sama sekali → lockout
            return HttpResponse(_LOCKOUT_PAGE, status=503,
                                content_type='text/html; charset=utf-8')

        block = _wm_extract_block(html)
        if not block:
            return HttpResponse(_LOCKOUT_PAGE, status=503,
                                content_type='text/html; charset=utf-8')

        current_hash = _wm_compute_hash(block)
        if current_hash != ref_hash:
            return HttpResponse(_LOCKOUT_PAGE, status=503,
                                content_type='text/html; charset=utf-8')

        return self.get_response(request)
