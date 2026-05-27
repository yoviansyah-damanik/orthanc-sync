import os
import json
import requests
import secrets
from datetime import datetime, timedelta
from functools import wraps

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.conf import settings

from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid, ImplicitVRLittleEndian
from pydicom.sequence import Sequence

from .models import APIKey, SystemConfig, WorklistLog, Worklist

def get_worklist_dir():
    return SystemConfig.get_val('WORKLIST_DIR', 'C:/Orthanc/Worklists')

# Decorator untuk validasi API Key pada endpoint eksternal
def api_key_required(f):
    @wraps(f)
    def decorated_function(request, *args, **kwargs):
        api_key_header = request.headers.get('X-API-Key')
        if not api_key_header:
            return JsonResponse({"success": False, "message": "API Key is missing"}, status=401)
        
        try:
            key_obj = APIKey.objects.get(key=api_key_header, is_active=True)
            key_obj.last_used = timezone.now()
            key_obj.save()
            request.api_key = key_obj # Simpan di request untuk digunakan di view
        except APIKey.DoesNotExist:
            return JsonResponse({"success": False, "message": "Invalid or inactive API Key"}, status=403)
            
        return f(request, *args, **kwargs)
    return decorated_function

# Decorator untuk validasi API Key ATAU Login Session
def api_key_or_login_required(f):
    @wraps(f)
    def decorated_function(request, *args, **kwargs):
        # 1. Cek Login Session
        if request.user.is_authenticated:
            return f(request, *args, **kwargs)
            
        # 2. Cek API Key jika belum login
        api_key_header = request.headers.get('X-API-Key')
        if not api_key_header:
            return JsonResponse({"success": False, "message": "Authentication required (Login or API Key)"}, status=401)
        
        try:
            key_obj = APIKey.objects.get(key=api_key_header, is_active=True)
            key_obj.last_used = timezone.now()
            key_obj.save()
            request.api_key = key_obj
        except APIKey.DoesNotExist:
            return JsonResponse({"success": False, "message": "Invalid or inactive API Key"}, status=403)
            
        return f(request, *args, **kwargs)
    return decorated_function

# --- AUTH VIEWS ---

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Username atau password salah")
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

# --- PAGE VIEWS ---

@login_required
def dashboard_view(request):
    logs = WorklistLog.objects.all()
    worklists = Worklist.objects.all()
    
    # Statistik Dasar
    stats = {
        'total_logs': logs.count(),
        'total_worklist': worklists.count(),
        'success_logs': logs.filter(status='Berhasil').count(),
        'failed_logs': logs.filter(status='Gagal').count(),
    }

    # Data Grafik Aktivitas (7 hari terakhir)
    last_7_days = timezone.now().date() - timedelta(days=6)
    daily_activity = logs.filter(created_at__date__gte=last_7_days) \
        .annotate(date=TruncDate('created_at')) \
        .values('date') \
        .annotate(count=Count('id')) \
        .order_by('date')

    # Siapkan data untuk Chart.js
    chart_labels = []
    chart_data = []
    
    # Isi data untuk setiap hari dalam 7 hari terakhir (termasuk yang kosong)
    date_map = {item['date']: item['count'] for item in daily_activity}
    for i in range(7):
        current_date = last_7_days + timedelta(days=i)
        chart_labels.append(current_date.strftime('%d %b'))
        chart_data.append(date_map.get(current_date, 0))

    context = {
        'logs': logs,
        'stats': stats,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'summary.html', context)

@login_required
def worklist_page_view(request):
    # Tampilkan data worklist yang tersimpan/aktif
    items = Worklist.objects.all()
    
    # Statistik untuk Stat Cards
    today = timezone.now().date()
    stats = {
        'total': items.count(),
        'today': items.filter(created_at__date=today).count(),
        'success': items.filter(status__in=['Berhasil', 'Updated']).count(),
        'failed': items.filter(status='Gagal').count(),
    }
    
    return render(request, 'worklist.html', {'logs': items, 'stats': stats})

@login_required
def api_logs_page_view(request):
    # Tampilkan semua log termasuk yang gagal dan dihapus
    logs = WorklistLog.objects.all()
    return render(request, 'api_logs.html', {'logs': logs})

@login_required
def api_docs_page_view(request):
    return render(request, 'api_docs.html')

@login_required
def api_management_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name')
            webhook_url = request.POST.get('webhook_url')
            APIKey.objects.create(name=name, webhook_url=webhook_url)
            messages.success(request, f"API Key untuk '{name}' berhasil dibuat")
        elif action == 'toggle':
            key_id = request.POST.get('key_id')
            key_obj = APIKey.objects.get(id=key_id)
            key_obj.is_active = not key_obj.is_active
            key_obj.save()
        elif action == 'delete':
            key_id = request.POST.get('key_id')
            APIKey.objects.get(id=key_id).delete()
            
        return redirect('api_management')

    keys = APIKey.objects.all().order_by('-created_at')
    return render(request, 'api_management.html', {'keys': keys})

# --- API ENDPOINTS ---

@csrf_exempt
@api_key_required
@require_http_methods(["POST", "PUT"])
def create_worklist_api(request):
    try:
        data = json.loads(request.body)
        
        # Ekstrak dan bersihkan data
        accession_number = str(data.get('accession_number', '')).strip()
        patient_id = str(data.get('patient_id', '')).strip()
        patient_name = str(data.get('patient_name', '')).strip()
        birth_date = data.get('birth_date')
        gender = data.get('gender')
        modality = data.get('modality')
        procedure_desc = data.get('procedure_desc')
        scheduled_date = data.get('scheduled_date')
        ae_title = data.get('ae_title', 'ANYMODALITY')
        study_instance_uid = data.get('study_instance_uid')
        
        # Gunakan webhook dari request, jika tidak ada pakai default dari API Key
        webhook_url = data.get('webhook_url') or (request.api_key.webhook_url if hasattr(request, 'api_key') else None)

        # Validasi dasar
        required_fields = {
            'accession_number': accession_number,
            'patient_id': patient_id,
            'patient_name': patient_name,
            'modality': modality,
            'scheduled_date': scheduled_date
        }
        
        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            error_msg = f"Data tidak lengkap. Field wajib berikut kosong atau tidak valid: {', '.join(missing_fields)}"
            # Log Gagal ke Database
            WorklistLog.objects.create(
                accession_number=accession_number or 'UNKNOWN',
                patient_name=patient_name or 'UNKNOWN',
                method=request.method,
                status="Gagal",
                raw_payload=request.body.decode('utf-8') if request.body else None,
                error_message=error_msg
            )
            return JsonResponse({
                "success": False,
                "message": error_msg
            }, status=400)

        # Persiapan Folder
        worklist_dir = get_worklist_dir()
        if not os.path.exists(worklist_dir):
            os.makedirs(worklist_dir)
            
        filepath = os.path.join(worklist_dir, f"{accession_number}.wl")

        # Cek apakah accession_number sudah ada (mencegah duplikasi)
        # Bypass diizinkan jika secara eksplisit mengirimkan parameter bypass: true dalam JSON
        # atau jika memanggil endpoint menggunakan method PUT
        is_bypass = data.get('bypass', False) or request.method == 'PUT'
        
        if not is_bypass and (Worklist.objects.filter(accession_number=accession_number).exists() or os.path.exists(filepath)):
            error_msg = f"Worklist dengan Accession Number {accession_number} sudah ada."
            # Log percobaan duplikasi ke Database (Audit Trail)
            WorklistLog.objects.create(
                accession_number=accession_number,
                patient_name=patient_name,
                method=request.method,
                status="Duplikat",
                raw_payload=request.body.decode('utf-8') if request.body else None,
                error_message=error_msg
            )
            return JsonResponse({
                "success": False,
                "message": error_msg
            }, status=409)

        # Meta Information DICOM
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.31'
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        file_meta.ImplementationClassUID = '1.2.826.0.1.3680043.8.498.1'
        file_meta.SourceApplicationEntityTitle = 'ORTHANC'
        
        ds = FileDataset(filepath, {}, file_meta=file_meta, preamble=b'\x00' * 128)
        
        # Karakter Set yang Digunakan (UTF-8 untuk dukungan karakter luas)
        ds.SpecificCharacterSet = 'ISO_IR 192'

        # Demografi Pasien
        # DICOM PN format: Family^Given^Middle^Prefix^Suffix
        adjusted_patient_name = patient_name.upper().strip().replace(' ', '^')
        ds.PatientName = adjusted_patient_name
        ds.PatientID = patient_id
        ds.PatientBirthDate = birth_date.replace('-', '') if birth_date else ''
        ds.PatientSex = gender.upper() if gender else ''
        
        # Kosongkan atau hapus tag opsional yang tidak ada datanya
        ds.MedicalAlerts = ''
        # PregnancyStatus (US), PatientWeight (DS), PatientSize (DS) adalah numerik/decimal
        # Sebaiknya tidak diisi jika kosong untuk menghindari error parsing pada beberapa modality
        if data.get('patient_weight'): ds.PatientWeight = str(data.get('patient_weight'))
        if data.get('patient_size'): ds.PatientSize = str(data.get('patient_size'))

        # Informasi Tindakan dan Order
        final_study_uid = study_instance_uid if study_instance_uid else generate_uid()
        ds.StudyInstanceUID = final_study_uid
        ds.AccessionNumber = accession_number[:16] # Batasi 16 karakter sesuai standar SH
        ds.RequestedProcedureID = accession_number[:16]
        ds.RequestedProcedureDescription = procedure_desc if procedure_desc else ''
        ds.RequestedProcedurePriority = 'ROUTINE'
        ds.ReferringPhysicianName = ''
        ds.RequestingPhysician = ''
        ds.AdmissionID = ''

        # Scheduled Procedure Step
        sps = Dataset()
        sps.Modality = modality.upper() if modality else ''
        sps.ScheduledStationAETitle = ae_title
        sps.ScheduledStationName = ''
        sps.ScheduledProcedureStepStartDate = scheduled_date.replace('-', '') if scheduled_date else ''
        sps.ScheduledProcedureStepStartTime = '000000'
        sps.ScheduledProcedureStepID = accession_number[:16]
        sps.ScheduledProcedureStepDescription = procedure_desc if procedure_desc else ''
        sps.ScheduledPerformingPhysicianName = ''
        sps.ScheduledProcedureStepLocation = ''
        sps.PreMedication = ''
        sps.ScheduledProcedureStepStatus = 'SCHEDULED'
        
        ds.ScheduledProcedureStepSequence = Sequence([sps])
        
        # Simpan File
        ds.is_little_endian = True
        ds.is_implicit_VR = True
        ds.save_as(filepath)

        # 1. Simpan/Update data aktif ke model Worklist
        # Periksa apakah ini update atau insert untuk kepentingan logging & response
        is_update = Worklist.objects.filter(accession_number=accession_number).exists()
        final_status = "Updated" if is_update else "Berhasil"
        
        Worklist.objects.update_or_create(
            accession_number=accession_number,
            defaults={
                'patient_id': patient_id,
                'patient_name': adjusted_patient_name,
                'birth_date': birth_date,
                'gender': gender,
                'procedure_desc': procedure_desc,
                'scheduled_date': scheduled_date,
                'modality': modality,
                'ae_title': ae_title,
                'study_instance_uid': final_study_uid,
                'file_path': filepath,
                'status': final_status,
                'is_active': True
            }
        )

        # 2. Catat Histori ke model WorklistLog (Audit Trail)
        WorklistLog.objects.create(
            accession_number=accession_number,
            patient_name=adjusted_patient_name,
            method=request.method,
            status=final_status,
            raw_payload=request.body.decode('utf-8') if request.body else None
        )

        # Trigger Webhook jika disediakan
        if webhook_url:
            try:
                requests.post(webhook_url, json={
                    "accession_number": accession_number,
                    "status": final_status,
                    "message": f"Worklist berhasil {'diupdate' if is_update else 'dibuat'}"
                }, timeout=5)
            except Exception as w_e:
                print(f"Gagal mengirim webhook sukses: {w_e}")

        return JsonResponse({
            "success": True, 
            "message": f"Worklist berhasil {'diupdate' if is_update else 'dibuat'}", 
            "accession_number": accession_number,
            "is_update": is_update
        })

    except Exception as e:
        # Jika gagal di fase membaca JSON, mungkin data tertentu kosong
        acc_num = data.get('accession_number', 'UNKNOWN') if 'data' in locals() else 'UNKNOWN'
        p_name = data.get('patient_name', 'UNKNOWN') if 'data' in locals() else 'UNKNOWN'
        
        # Log Gagal ke Database
        WorklistLog.objects.create(
            accession_number=acc_num,
            patient_name=p_name,
            method=request.method,
            status="Gagal",
            raw_payload=request.body.decode('utf-8') if hasattr(request, 'body') and request.body else None,
            error_message=str(e)
        )
        
        # Trigger Webhook jika disediakan
        webhook_url = data.get('webhook_url') if 'data' in locals() and isinstance(data, dict) else None
        if webhook_url:
            try:
                requests.post(webhook_url, json={
                    "accession_number": acc_num,
                    "status": "Gagal",
                    "message": str(e)
                }, timeout=5)
            except Exception as w_e:
                print(f"Gagal mengirim webhook error: {w_e}")
                
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)

@csrf_exempt
@api_key_required
@require_http_methods(["GET", "DELETE"])
def worklist_detail_api(request, accession_number):
    # Cari di database dulu
    try:
        item = Worklist.objects.get(accession_number=accession_number)
        filepath = item.file_path
    except Worklist.DoesNotExist:
        filepath = os.path.join(get_worklist_dir(), f"{accession_number}.wl")
        item = None
    
    if request.method == "GET":
        if item or os.path.exists(filepath):
            return JsonResponse({
                "success": True,
                "message": "Worklist ditemukan",
                "data": {
                    "accession_number": accession_number,
                    "patient_name": item.patient_name if item else "Unknown",
                    "file_path": filepath,
                    "created_at": item.created_at.isoformat() if item else os.path.getctime(filepath)
                }
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "Worklist tidak ditemukan"
            }, status=404)
            
    elif request.method == "DELETE":
        # Hapus file fisik
        file_deleted = False
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                file_deleted = True
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Gagal hapus file: {str(e)}"}, status=500)

        # Hapus data dari model Worklist
        if item:
            item.delete()

        # Catat ke log audit
        WorklistLog.objects.create(
            accession_number=accession_number,
            patient_name=item.patient_name if item else "Unknown",
            method=request.method,
            status="Dihapus",
            error_message="Dihapus via API"
        )

        return JsonResponse({
            "success": True,
            "message": "Worklist berhasil dihapus" if file_deleted or item else "Tidak ada data untuk dihapus"
        })

@csrf_exempt
@api_key_required
@require_http_methods(["GET"])
def health_check_api(request):
    """
    Endpoint untuk mengecek status kesehatan sistem Orthanc Bridge.
    """
    import platform
    import django
    from django.db import connection
    
    status = {
        "status": "online",
        "timestamp": timezone.now().isoformat(),
        "database": "unknown",
        "storage": "unknown",
        "system": {
            "python": platform.python_version(),
            "django": django.get_version(),
            "os": platform.system()
        }
    }

    # Cek Database
    try:
        connection.ensure_connection()
        status["database"] = "connected"
    except Exception as e:
        status["database"] = f"error: {str(e)}"
        status["status"] = "degraded"

    # Cek Storage (Folder Worklist)
    worklist_dir = get_worklist_dir()
    if os.path.exists(worklist_dir):
        if os.access(worklist_dir, os.W_OK): # W_OK is for writable
            status["storage"] = "writable"
        else:
            status["storage"] = "readable but not writable"
            status["status"] = "degraded"
    else:
        status["storage"] = "not found"
        status["status"] = "error"

    return JsonResponse(status)

@login_required
def configuration_view(request):
    """
    Halaman konfigurasi sistem.
    """
    if request.method == "POST":
        # Simpan pengaturan
        for key, value in request.POST.items():
            if key == 'csrfmiddlewaretoken': continue
            config, created = SystemConfig.objects.get_or_create(key=key)
            config.value = value
            config.save()
        messages.success(request, "Konfigurasi berhasil diperbarui")
        return redirect('configuration_page')

    configs = SystemConfig.objects.all().order_by('key')
    return render(request, 'configuration.html', {'configs': configs})

@login_required
def test_orthanc_connection(request):
    """
    Mengetes koneksi ke REST API Orthanc.
    """
    url = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
    user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
    password = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
    
    try:
        # Panggil endpoint /system untuk cek koneksi
        response = requests.get(
            f"{url.rstrip('/')}/system",
            auth=(user, password),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return JsonResponse({
                "success": True, 
                "message": f"Koneksi Berhasil! Orthanc v{data.get('Version', 'Unknown')} terdeteksi."
            })
        else:
            return JsonResponse({
                "success": False, 
                "message": f"Koneksi Gagal: Status {response.status_code}"
            })
    except Exception as e:
        return JsonResponse({
            "success": False, 
            "message": f"Koneksi Gagal: {str(e)}"
        })

@login_required
def fix_folder_permissions(request):
    """
    Mencoba membuat folder dan memberikan izin akses penuh (Windows/Linux).
    """
    worklist_dir = get_worklist_dir()
    
    try:
        # 1. Pastikan folder ada
        if not os.path.exists(worklist_dir):
            os.makedirs(worklist_dir, exist_ok=True)
            
        # 2. Setel Izin Akses
        import subprocess
        if os.name == 'nt':
            # Windows: Berikan Full Control ke Everyone secara rekursif
            # /grant Everyone:(OI)(CI)F -> OI (Object Inherit), CI (Container Inherit), F (Full Access)
            cmd = f'icacls "{worklist_dir}" /grant Everyone:(OI)(CI)F /T /C /Q'
            subprocess.run(cmd, shell=True, check=True)
        else:
            # Linux/Unix: Setel permission 777 agar bisa dibaca/tulis oleh siapapun (termasuk Orthanc)
            cmd = f'chmod -R 777 "{worklist_dir}"'
            subprocess.run(cmd, shell=True, check=True)
            
        # 3. Verifikasi Akhir (Cek apakah benar-benar writable)
        test_file = os.path.join(worklist_dir, '.permission_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
            
        return JsonResponse({
            "success": True, 
            "message": f"Hak akses folder '{worklist_dir}' telah disetel dan diverifikasi (RW)."
        })
    except Exception as e:
        return JsonResponse({
            "success": False, 
            "message": f"Gagal menyetel hak akses: {str(e)}"
        })

@login_required
def profile_view(request):
    """
    Halaman profil untuk merubah data user.
    """
    if request.method == "POST":
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        user = request.user
        
        # Update basic info
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        
        # Update password if provided
        if new_password:
            if new_password == confirm_password:
                user.set_password(new_password)
                user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user) # Biar ga logout otomatis
                messages.success(request, "Profil dan password berhasil diperbarui.")
            else:
                messages.error(request, "Password baru tidak cocok.")
                return redirect('profile_page')
        else:
            user.save()
            messages.success(request, "Profil berhasil diperbarui.")
            
        return redirect('profile_page')

    return render(request, 'profile.html')

@login_required
def worklist_history_view(request, accession_number):
    """Mengambil riwayat log untuk accession number tertentu"""
    logs = WorklistLog.objects.filter(accession_number=accession_number).order_by('-created_at')
    data = []
    for log in logs:
        data.append({
            'id': log.id,
            'status': log.status,
            'method': log.method,
            'time': log.created_at.strftime('%H:%M:%S %d %b %Y'),
            'error': log.error_message,
            'payload': log.raw_payload
        })
    return JsonResponse({'success': True, 'history': data})

import subprocess

def database_setup_page(request):
    """Halaman instruksi jika database belum siap"""
    return render(request, 'setup_database.html')

from .utils import execute_database_setup, test_db_connection, update_env_file
import json

def run_database_setup(request):
    """Endpoint untuk menjalankan migrasi dan seeder dari UI"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            # Update .env first
            env_updates = {
                'DB_HOST': data.get('host', '127.0.0.1'),
                'DB_PORT': data.get('port', '3306'),
                'DB_USER': data.get('user', 'root'),
                'DB_PASSWORD': data.get('password', ''),
                'DB_NAME': data.get('db_name', 'orthanc_sync')
            }
            update_env_file(env_updates)
            
            # Then run setup
            success, message = execute_database_setup()
            return JsonResponse({"success": success, "message": message})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
            
    return JsonResponse({"success": False, "message": "Method not allowed"})

def test_db_api(request):
    """Endpoint untuk tes koneksi database sebelum disimpan"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            success, message = test_db_connection(
                host=data.get('host'),
                port=data.get('port'),
                user=data.get('user'),
                password=data.get('password'),
                db_name=data.get('db_name')
            )
            return JsonResponse({"success": success, "message": message})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return JsonResponse({"success": False, "message": "Method not allowed"})

def check_db_health(request):
    """Cek status koneksi database aktif"""
    from django.db import connection
    from .utils import scan_local_database_ports
    
    engine = connection.vendor # 'mysql' or 'sqlite'
    settings = connection.settings_dict
    
    status = {
        "engine": engine,
        "host": settings.get('HOST', 'localhost'),
        "port": settings.get('PORT', ''),
        "is_ready": False,
        "can_connect": False,
        "tables_exist": False,
        "available_services": scan_local_database_ports()
    }
    
    try:
        with connection.cursor() as cursor:
            status["can_connect"] = True
            # Cek tabel bridge_user
            if engine == 'mysql':
                cursor.execute("SHOW TABLES LIKE 'bridge_user'")
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bridge_user'")
            
            if cursor.fetchone():
                status["tables_exist"] = True
                status["is_ready"] = True
    except:
        status["can_connect"] = False

    return JsonResponse(status)
    
@api_key_or_login_required
def check_worklist_file_api(request, accession_number):
    """
    Mengecek apakah file .wl (DICOM Worklist) untuk accession number tertentu 
    tersedia secara fisik di folder Worklist.
    """
    wl_dir = get_worklist_dir()
    file_name = f"{accession_number}.wl"
    file_path = os.path.join(wl_dir, file_name)
    
    exists_physically = os.path.exists(file_path)
    
    # Cek juga di database untuk informasi tambahan
    try:
        wl_obj = Worklist.objects.filter(accession_number=accession_number, is_active=True).first()
        if wl_obj:
            return JsonResponse({
                "success": True,
                "exists": True,
                "file_name": file_name,
                "file_path": file_path if exists_physically else (wl_obj.file_path or "Unknown"),
                "physically_present": exists_physically,
                "database_record": True,
                "patient_name": wl_obj.patient_name,
                "modality": wl_obj.modality,
                "created_at": wl_obj.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
    except Exception:
        pass
        
    return JsonResponse({
        "success": True,
        "exists": exists_physically,
        "file_name": file_name,
        "physically_present": exists_physically,
        "database_record": False
    })

@api_key_or_login_required
def check_orthanc_study_api(request, accession_number):
    """
    Mengecek apakah study untuk accession number tertentu sudah masuk ke Orthanc.
    """
    url = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
    user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
    pw = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
    
    try:
        # 1. Cari Study berdasarkan AccessionNumber
        query = {
            "Level": "Study",
            "Query": {"AccessionNumber": accession_number}
        }
        r = requests.post(
            f"{url.rstrip('/')}/tools/find", 
            auth=(user, pw), 
            json=query, 
            timeout=3
        )
        
        if r.status_code == 200:
            study_ids = r.json()
            if study_ids:
                # 2. Ambil detail study pertama yang ditemukan
                study_id = study_ids[0]
                s_info = requests.get(
                    f"{url.rstrip('/')}/studies/{study_id}", 
                    auth=(user, pw), 
                    timeout=3
                ).json()
                
                # 3. Hitung series dan instances secara terperinci
                series_resp = requests.get(
                    f"{url.rstrip('/')}/studies/{study_id}/series", 
                    auth=(user, pw), 
                    timeout=3
                )
                
                series_data = []
                instances_count = 0
                modalities = set()
                
                if series_resp.status_code == 200:
                    for s in series_resp.json():
                        series_id = s.get('ID')
                        instances_in_series = len(s.get('Instances', []))
                        instances_count += instances_in_series
                        s_tags = s.get('MainDicomTags', {})
                        
                        # Fetch instance details for this series
                        instances_data = []
                        if series_id:
                            try:
                                inst_resp = requests.get(
                                    f"{url.rstrip('/')}/series/{series_id}/instances", 
                                    auth=(user, pw), 
                                    timeout=3
                                )
                                if inst_resp.status_code == 200:
                                    for inst in inst_resp.json():
                                        i_tags = inst.get('MainDicomTags', {})
                                        instances_data.append({
                                            "instance_id": inst.get('ID'),
                                            "instance_number": i_tags.get('InstanceNumber', '-'),
                                            "sop_instance_uid": i_tags.get('SOPInstanceUID', '-'),
                                            "creation_time": i_tags.get('InstanceCreationTime', '-')
                                        })
                            except:
                                pass
                                
                        modality = s_tags.get('Modality', '-')
                        if modality != '-':
                            modalities.add(modality)

                        series_data.append({
                            "series_id": series_id,
                            "series_instance_uid": s_tags.get('SeriesInstanceUID', '-'),
                            "series_number": s_tags.get('SeriesNumber', '-'),
                            "modality": modality,
                            "series_description": s_tags.get('SeriesDescription', '-'),
                            "instances_count": instances_in_series,
                            "instances": instances_data
                        })
                
                # Fallback jika endpoint series gagal atau kosong tapi sebenarnya ada instances
                if instances_count == 0 and len(s_info.get('Series', [])) == 0:
                    instances_resp = requests.get(
                        f"{url.rstrip('/')}/studies/{study_id}/instances", 
                        auth=(user, pw), 
                        timeout=3
                    )
                    instances_count = len(instances_resp.json()) if instances_resp.status_code == 200 else 0
                
                tags = s_info.get('MainDicomTags', {})
                p_tags = s_info.get('PatientMainDicomTags', {})
                return JsonResponse({
                    "success": True,
                    "exists": True,
                    "study_id": study_id,
                    "study_instance_uid": tags.get('StudyInstanceUID', '-'),
                    "patient_id": p_tags.get('PatientID', '-'),
                    "study_description": tags.get('StudyDescription', '-'),
                    "study_date": tags.get('StudyDate', '-'),
                    "study_time": tags.get('StudyTime', '-'),
                    "modality": list(modalities) if modalities else tags.get('ModalitiesInStudy', []),
                    "series_count": len(series_data),
                    "instances_count": instances_count,
                    "series_details": series_data
                })
        
        return JsonResponse({"success": True, "exists": False})
        
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

def error_404_view(request, exception):
    return render(request, '404.html', status=404)

def error_500_view(request):
    return render(request, '500.html', status=500)
