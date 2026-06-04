import os
import json
import requests
import urllib3
import secrets
import socket
import ipaddress
import concurrent.futures
from datetime import datetime, timedelta
from functools import wraps

# Abaikan warning SSL InsecureRequestWarning agar log konsol tetap bersih
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
from pynetdicom import AE
from pynetdicom.sop_class import Verification

from .models import APIKey, SystemConfig, WorklistLog, Worklist, DicomDevice, RoutingRule, RoutingLog, SyncSchedule, SyncLog

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
def monitoring_view(request):
    # Render halaman monitoring dengan grafik event aplikasi terintegrasi
    return render(request, 'monitoring.html')

@login_required
def monitoring_chart_api(request):
    """Endpoint JSON yang menyediakan semua data grafik monitoring secara terpusat dengan filter interval tanggal."""
    import datetime
    from django.db.models import Count

    logs = WorklistLog.objects.all()
    worklists = Worklist.objects.all()

    # --- Ambil Parameter Filter ---
    preset = request.GET.get('preset', '30d')
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    # Default date range
    today = timezone.now().date()
    start_date = today - timedelta(days=29) # Default 30 hari terakhir
    end_date = today

    if preset == 'today':
        start_date = today
        end_date = today
    elif preset == '7d':
        start_date = today - timedelta(days=6)
        end_date = today
    elif preset == '30d':
        start_date = today - timedelta(days=29)
        end_date = today
    elif preset == '90d':
        start_date = today - timedelta(days=89)
        end_date = today
    elif preset == 'custom' and start_str and end_str:
        try:
            start_date = datetime.datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Proteksi: pastikan start_date tidak mendahului end_date
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # Filter querysets berdasarkan rentang tanggal
    # Gunakan timezone-aware datetime range (created_at__range) untuk menghindari pemanggilan CONVERT_TZ MySQL
    from django.utils.timezone import make_aware
    start_dt = make_aware(datetime.datetime.combine(start_date, datetime.time.min))
    end_dt = make_aware(datetime.datetime.combine(end_date, datetime.time.max))

    logs_filtered = logs.filter(created_at__range=[start_dt, end_dt])
    worklists_filtered = worklists.filter(created_at__range=[start_dt, end_dt])

    # --- 1. Aktivitas Harian ---
    # Kelompokkan di sisi Python untuk menghindari ketergantungan pada tabel timezone MySQL
    daily_logs = logs_filtered.values_list('created_at', flat=True)
    
    date_map = {}
    for dt in daily_logs:
        if dt:
            local_dt = dt.astimezone(timezone.get_current_timezone())
            d = local_dt.date()
            date_map[d] = date_map.get(d, 0) + 1

    # Hitung jumlah hari di antara rentang tanggal yang dipilih
    days_diff = (end_date - start_date).days
    daily_labels, daily_data = [], []
    for i in range(days_diff + 1):
        d = start_date + timedelta(days=i)
        daily_labels.append(d.strftime('%d %b'))
        daily_data.append(date_map.get(d, 0))

    # --- 2. Distribusi Status ---
    status_qs = logs_filtered.values('status').annotate(count=Count('id')).order_by('-count')
    status_labels = [s['status'] for s in status_qs]
    status_data   = [s['count'] for s in status_qs]

    # --- 3. Distribusi Method HTTP ---
    method_qs = logs_filtered.values('method').annotate(count=Count('id')).order_by('-count')
    method_labels = [m['method'] for m in method_qs]
    method_data   = [m['count'] for m in method_qs]

    # --- 4. Top Modality ---
    modality_qs = (
        worklists_filtered.exclude(modality='')
        .values('modality').annotate(count=Count('id')).order_by('-count')[:8]
    )
    modality_labels = [m['modality'] for m in modality_qs]
    modality_data   = [m['count'] for m in modality_qs]

    # --- 5. Distribusi Per Jam ---
    all_created_at = logs_filtered.values_list('created_at', flat=True)
    hour_map = {}
    for dt in all_created_at:
        if dt:
            local_dt = dt.astimezone(timezone.get_current_timezone())
            h = local_dt.hour
            hour_map[h] = hour_map.get(h, 0) + 1

    hour_labels = [f"{h:02d}:00" for h in range(24)]
    hour_data   = [hour_map.get(h, 0) for h in range(24)]

    # --- 6. Statistik ringkasan dalam interval yang dipilih ---
    # Hitung logs hari ini secara aman menggunakan range datetime hari ini
    today_start = make_aware(datetime.datetime.combine(today, datetime.time.min))
    today_end = make_aware(datetime.datetime.combine(today, datetime.time.max))
    logs_today_count = logs.filter(created_at__range=[today_start, today_end]).count()

    summary = {
        'total_logs':      logs_filtered.count(),
        'logs_today':      logs_today_count,
        'success_count':   logs_filtered.filter(status__in=['Berhasil', 'Updated']).count(),
        'failed_count':    logs_filtered.filter(status='Gagal').count(),
        'active_worklist': worklists.filter(is_active=True).count(), # Tetap gunakan real-time global active count
        'total_worklist':  worklists.count(), # Tetap gunakan real-time global total
    }

    return JsonResponse({
        'summary':         summary,
        'daily_labels':    daily_labels,
        'daily_data':      daily_data,
        'status_labels':   status_labels,
        'status_data':     status_data,
        'method_labels':   method_labels,
        'method_data':     method_data,
        'modality_labels': modality_labels,
        'modality_data':   modality_data,
        'hour_labels':     hour_labels,
        'hour_data':       hour_data,
    })


@login_required
def api_docs_page_view(request):
    return render(request, 'api_docs.html')

@login_required
def user_guide_page_view(request):
    # Render halaman petunjuk penggunaan aplikasi untuk operator klinis
    return render(request, 'user_guide.html')

@login_required
def api_management_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name')
            webhook_url = request.POST.get('webhook_url')
            webhook_username = request.POST.get('webhook_username') or None
            webhook_password = request.POST.get('webhook_password') or None
            APIKey.objects.create(
                name=name,
                webhook_url=webhook_url,
                webhook_username=webhook_username,
                webhook_password=webhook_password
            )
            messages.success(request, f"API Key untuk '{name}' berhasil dibuat")
        elif action == 'toggle':
            key_id = request.POST.get('key_id')
            key_obj = APIKey.objects.get(id=key_id)
            key_obj.is_active = not key_obj.is_active
            key_obj.save()
        elif action == 'delete':
            key_id = request.POST.get('key_id')
            APIKey.objects.get(id=key_id).delete()
        elif action == 'update':
            key_id = request.POST.get('key_id')
            try:
                key_obj = APIKey.objects.get(id=key_id)
                key_obj.name = request.POST.get('name')
                key_obj.webhook_url = request.POST.get('webhook_url') or None
                
                # Logika update username & password
                new_username = request.POST.get('webhook_username') or None
                new_password = request.POST.get('webhook_password')
                
                key_obj.webhook_username = new_username
                if not new_username:
                    key_obj.webhook_password = None
                elif new_password: # Hanya update password jika diisi nilai baru
                    key_obj.webhook_password = new_password
                
                key_obj.save()
                messages.success(request, f"API Key untuk '{key_obj.name}' berhasil diperbarui")
            except APIKey.DoesNotExist:
                messages.error(request, "API Key tidak ditemukan")
        elif action == 'test_webhook':
            key_id = request.POST.get('key_id')
            try:
                key_obj = APIKey.objects.get(id=key_id)
                if not key_obj.webhook_url:
                    return JsonResponse({"success": False, "message": "URL Webhook belum diatur untuk API Key ini."})
                
                # Kirim data testing ke webhook menggunakan Basic Auth jika tersedia
                wh_auth = None
                wh_user = None
                wh_pass = None
                if key_obj.webhook_username:
                    wh_user = key_obj.webhook_username
                    wh_pass = key_obj.webhook_password or ''
                    wh_auth = (wh_user, wh_pass)
                
                payload = {
                    "accession_number": "TEST-123456",
                    "status": "Test",
                    "message": "Uji koneksi (test hit) dari Orthanc Bridge berhasil."
                }
                
                response = requests.post(
                    key_obj.webhook_url,
                    json=payload,
                    auth=wh_auth,
                    verify=False,
                    timeout=5
                )
                
                if 200 <= response.status_code < 300:
                    return JsonResponse({
                        "success": True,
                        "message": f"Koneksi webhook berhasil! Status Code: {response.status_code}"
                    })
                else:
                    return JsonResponse({
                        "success": False,
                        "message": f"Webhook merespon dengan status {response.status_code}. Response: {response.text[:100]}"
                    })
            except APIKey.DoesNotExist:
                return JsonResponse({"success": False, "message": "API Key tidak ditemukan."})
            except requests.exceptions.RequestException as re_err:
                return JsonResponse({
                    "success": False,
                    "message": f"Koneksi ke Webhook gagal/timeout: {str(re_err)}"
                })
            except Exception as ex:
                return JsonResponse({
                    "success": False,
                    "message": f"Terjadi kesalahan: {str(ex)}"
                })
            
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
                # Prioritaskan Basic Auth dari payload input, fallback ke database API Key
                wh_auth = None
                wh_user = None
                wh_pass = None
                p_user = data.get('webhook_username') if isinstance(data, dict) else None
                p_pass = data.get('webhook_password') if isinstance(data, dict) else None
                
                if p_user:
                    wh_user = p_user
                    wh_pass = p_pass or ''
                elif hasattr(request, 'api_key') and request.api_key.webhook_username:
                    wh_user = request.api_key.webhook_username
                    wh_pass = request.api_key.webhook_password or ''
                
                if wh_user:
                    wh_auth = (wh_user, wh_pass)
                
                requests.post(webhook_url, json={
                    "accession_number": accession_number,
                    "status": final_status,
                    "message": f"Worklist berhasil {'diupdate' if is_update else 'dibuat'}"
                }, auth=wh_auth, verify=False, timeout=5)
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
                # Prioritaskan Basic Auth dari payload input, fallback ke database API Key
                wh_auth = None
                wh_user = None
                wh_pass = None
                p_user = data.get('webhook_username') if isinstance(data, dict) else None
                p_pass = data.get('webhook_password') if isinstance(data, dict) else None
                
                if p_user:
                    wh_user = p_user
                    wh_pass = p_pass or ''
                elif hasattr(request, 'api_key') and request.api_key.webhook_username:
                    wh_user = request.api_key.webhook_username
                    wh_pass = request.api_key.webhook_password or ''
                
                if wh_user:
                    wh_auth = (wh_user, wh_pass)
                
                requests.post(webhook_url, json={
                    "accession_number": acc_num,
                    "status": "Gagal",
                    "message": str(e)
                }, auth=wh_auth, verify=False, timeout=5)
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
        from django.core.cache import cache
        cache.delete_many(['ctx_orthanc_creds', 'ctx_orthanc_status'])
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

# --- ALL STUDIES ---

@login_required
def all_studies_view(request):
    """Render halaman daftar seluruh study dari Orthanc."""
    orthanc_url = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
    devices = DicomDevice.objects.all()
    return render(request, 'all_studies.html', {
        'orthanc_url': orthanc_url,
        'devices': devices
    })

@login_required
def orthanc_viewer_url_api(request):
    """
    API AJAX: Mendeteksi plugin viewer Orthanc yang terinstall dan
    mengembalikan URL viewer yang tepat untuk suatu study.
    """
    study_id = request.GET.get('study_id', '')
    url  = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
    user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
    pw   = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')

    if not study_id:
        return JsonResponse({'success': False, 'message': 'study_id diperlukan'}, status=400)

    try:
        # Ambil daftar plugin yang terinstall di Orthanc
        plugins_resp = requests.get(
            f"{url.rstrip('/')}/plugins",
            auth=(user, pw),
            timeout=5
        )
        installed_plugins = plugins_resp.json() if plugins_resp.status_code == 200 else []

        clean_url = url.rstrip('/')

        # Urutan prioritas deteksi plugin viewer berdasarkan yang paling umum
        # Stone Web Viewer (resmi & modern)
        if 'stone-webviewer' in installed_plugins:
            viewer_url = f"{clean_url}/stone-webviewer/index.html?study={study_id}"
        # Osimis Web Viewer
        elif 'osimis-web-viewer' in installed_plugins:
            viewer_url = f"{clean_url}/osimis-viewer/app/index.html?study={study_id}"
        # Orthanc Web Viewer (legacy)
        elif 'web-viewer' in installed_plugins:
            viewer_url = f"{clean_url}/web-viewer/app/index.html?studyId={study_id}"
        # Fallback: gunakan interface Orthanc Explorer langsung
        else:
            viewer_url = f"{clean_url}/app/explorer.html#study?uuid={study_id}"

        return JsonResponse({
            'success': True,
            'viewer_url': viewer_url,
            'installed_plugins': installed_plugins,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def orthanc_studies_api(request):
    """
    API AJAX: Mengambil daftar seluruh study dari Orthanc.
    Mendukung parameter ?search= untuk filter sisi server.
    """
    url    = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
    user   = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
    pw     = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
    search = request.GET.get('search', '').strip()

    try:
        # Gunakan /tools/find agar hasil lebih terstruktur
        query_payload = {
            "Level": "Study",
            "Expand": True,
            "Query": {}
        }
        if search:
            # Coba cocokkan dengan berbagai field utama
            query_payload["Query"] = {"PatientName": f"*{search}*"}

        r = requests.post(
            f"{url.rstrip('/')}/tools/find",
            auth=(user, pw),
            json=query_payload,
            timeout=10
        )

        if r.status_code != 200:
            return JsonResponse({"success": False, "message": f"Orthanc merespon {r.status_code}"}, status=502)

        raw_studies = r.json()
        studies = []
        for s in raw_studies:
            tags   = s.get('MainDicomTags', {})
            p_tags = s.get('PatientMainDicomTags', {})

            # Format tanggal YYYYMMDD → DD-MM-YYYY
            raw_date = tags.get('StudyDate', '')
            if raw_date and len(raw_date) == 8:
                fmt_date = f"{raw_date[6:8]}-{raw_date[4:6]}-{raw_date[:4]}"
            else:
                fmt_date = raw_date or '-'

            # Hitung jumlah series dan instances dari metadata Orthanc
            series_ids = s.get('Series', [])
            series_count = len(series_ids)

            modalities_raw = tags.get('ModalitiesInStudy', '') or tags.get('Modality', '')
            if isinstance(modalities_raw, list):
                modalities = modalities_raw
            elif modalities_raw:
                modalities = [m.strip() for m in modalities_raw.replace('\\', ',').split(',') if m.strip()]
            else:
                modalities = []

            # Fallback 1: Coba ambil modality dari series pertama jika kosong
            if not modalities and series_ids:
                try:
                    first_series_id = series_ids[0]
                    ser_resp = requests.get(
                        f"{url.rstrip('/')}/series/{first_series_id}",
                        auth=(user, pw),
                        timeout=2
                    )
                    if ser_resp.status_code == 200:
                        ser_tags = ser_resp.json().get('MainDicomTags', {})
                        ser_mod = ser_tags.get('Modality', '')
                        if ser_mod:
                            modalities = [ser_mod]
                except Exception:
                    pass

            # Fallback 2: Tebak dari Accession Number atau Description jika masih kosong
            if not modalities:
                acc = tags.get('AccessionNumber', '').upper()
                desc = tags.get('StudyDescription', '').upper()
                if acc.startswith('US') or 'USG' in desc or 'ULTRASOUND' in desc or 'ULTRASONOGRAPHY' in desc:
                    modalities = ['US']
                elif acc.startswith('CT') or 'CT' in desc:
                    modalities = ['CT']
                elif acc.startswith('MR') or 'MRI' in desc:
                    modalities = ['MR']
                elif acc.startswith('CR') or acc.startswith('DR') or 'XRAY' in desc or 'RONTGEN' in desc or 'ROENTGEN' in desc:
                    modalities = ['CR']

            studies.append({
                "study_id"         : s.get('ID', '-'),
                "patient_name"     : p_tags.get('PatientName', tags.get('PatientName', '-')).replace('^', ' ').strip(),
                "patient_id"       : p_tags.get('PatientID', tags.get('PatientID', '-')),
                "study_date"       : fmt_date,
                "study_description": tags.get('StudyDescription', '-'),
                "modality"         : modalities,
                "accession_number" : tags.get('AccessionNumber', '-'),
                "referring_physician": (tags.get('RequestingPhysician', '') or tags.get('ReferringPhysicianName', '') or '-').replace('^', ' ').strip() or '-',
                "series_count"     : series_count,
                "study_instance_uid": tags.get('StudyInstanceUID', '-'),
            })

        # Urutkan berdasarkan tanggal terbaru (raw date utk sorting)
        studies.sort(key=lambda x: x.get('study_date', ''), reverse=True)

        return JsonResponse({"success": True, "studies": studies, "total": len(studies)})

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

@login_required
def orthanc_study_detail_api(request, study_id):
    """
    API AJAX: Mengambil detail lengkap satu study dari Orthanc berdasarkan Orthanc Study ID.
    Termasuk seluruh series dan jumlah instances masing-masing.
    """
    url  = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
    user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
    pw   = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')

    try:
        # Detail study
        s_resp = requests.get(f"{url.rstrip('/')}/studies/{study_id}", auth=(user, pw), timeout=5)
        if s_resp.status_code != 200:
            return JsonResponse({"success": False, "message": "Study tidak ditemukan"}, status=404)
        s_info = s_resp.json()

        tags   = s_info.get('MainDicomTags', {})
        p_tags = s_info.get('PatientMainDicomTags', {})

        # Ambil detail series
        sr_resp = requests.get(f"{url.rstrip('/')}/studies/{study_id}/series", auth=(user, pw), timeout=5)
        series_list = []
        total_instances = 0
        if sr_resp.status_code == 200:
            for sr in sr_resp.json():
                s_tags = sr.get('MainDicomTags', {})
                inst_ids = sr.get('Instances', [])
                total_instances += len(inst_ids)
                series_list.append({
                    "series_id"         : sr.get('ID'),
                    "series_number"     : s_tags.get('SeriesNumber', '-'),
                    "series_description": s_tags.get('SeriesDescription', '-'),
                    "modality"          : s_tags.get('Modality', '-'),
                    "instances_count"   : len(inst_ids),
                    "series_instance_uid": s_tags.get('SeriesInstanceUID', '-'),
                })
            series_list.sort(key=lambda x: str(x.get('series_number', '0')))

        raw_date = tags.get('StudyDate', '')
        fmt_date = f"{raw_date[6:8]}-{raw_date[4:6]}-{raw_date[:4]}" if raw_date and len(raw_date) == 8 else (raw_date or '-')
        raw_time = tags.get('StudyTime', '')
        fmt_time = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}" if raw_time and len(raw_time) >= 6 else (raw_time or '-')

        return JsonResponse({
            "success"           : True,
            "study_id"          : study_id,
            "patient_name"      : p_tags.get('PatientName', '-').replace('^', ' ').strip(),
            "patient_id"        : p_tags.get('PatientID', '-'),
            "patient_birth_date": p_tags.get('PatientBirthDate', '-'),
            "patient_sex"       : p_tags.get('PatientSex', '-'),
            "study_date"        : fmt_date,
            "study_time"        : fmt_time,
            "study_description" : tags.get('StudyDescription', '-'),
            "accession_number"  : tags.get('AccessionNumber', '-'),
            "referring_physician": (tags.get('RequestingPhysician', '') or tags.get('ReferringPhysicianName', '') or '-').replace('^', ' ').strip() or '-',
            "study_instance_uid": tags.get('StudyInstanceUID', '-'),
            "total_series"      : len(series_list),
            "total_instances"   : total_instances,
            "series"            : series_list,
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def dicom_transfer_api(request):
    """
    API AJAX: Mengirimkan study dari Orthanc local ke node DICOM tujuan (C-STORE).
    """
    try:
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        study_id = data.get('study_id')
        device_id = data.get('device_id')

        if not study_id or not device_id:
            return JsonResponse({"success": False, "message": "Study ID dan Device ID wajib disertakan."}, status=400)

        # 1. Cari data DicomDevice dari database
        try:
            device = DicomDevice.objects.get(id=device_id)
        except DicomDevice.DoesNotExist:
            return JsonResponse({"success": False, "message": "Perangkat DICOM tidak ditemukan di database."}, status=404)

        # 2. Ambil kredensial & URL Orthanc lokal
        url  = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
        user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
        pw   = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
        clean_url = url.rstrip('/')

        # 3. Daftarkan/Perbarui remote modality di Orthanc dinamis via REST API
        modality_symbolic_name = f"device_{device.id.hex}"
        
        modality_payload = {
            "AET": device.ae_title,
            "Host": device.host,
            "Port": int(device.port),
            "Manufacturer": "Generic",
            "AllowEcho": True,
            "AllowStore": True
        }

        put_resp = requests.put(
            f"{clean_url}/modalities/{modality_symbolic_name}",
            auth=(user, pw),
            json=modality_payload,
            timeout=10
        )

        if put_resp.status_code not in (200, 201):
            return JsonResponse({
                "success": False,
                "message": f"Gagal meregistrasikan node tujuan di Orthanc: {put_resp.text}"
            }, status=500)

        # 4. Kirim perintah C-STORE push ke modality tersebut
        store_payload = [study_id]
        
        post_resp = requests.post(
            f"{clean_url}/modalities/{modality_symbolic_name}/store",
            auth=(user, pw),
            json=store_payload,
            timeout=120
        )

        if post_resp.status_code != 200:
            return JsonResponse({
                "success": False,
                "message": f"Gagal melakukan transfer DICOM: {post_resp.text}"
            }, status=500)

        store_result = post_resp.json()
        failed_count = store_result.get('FailedInstancesCount', 0)
        success_count = store_result.get('InstancesCount', 0) - failed_count

        if failed_count > 0:
            return JsonResponse({
                "success": False,
                "message": f"Transfer selesai dengan error: {failed_count} instance gagal dikirim."
            })

        return JsonResponse({
            "success": True,
            "message": f"Koneksi berhasil! {success_count} file DICOM berhasil dikirim ke {device.name} ({device.ae_title})."
        })

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

# Helper untuk mendapatkan local IP server
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# Helper untuk mendapatkan saran subnet (/24)
def get_suggested_subnet():
    try:
        local_ip = get_local_ip()
        parts = local_ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}"
    except Exception:
        pass
    return "192.168.1"

# Helper untuk mengecek koneksi port TCP
def check_host_port(ip, port, timeout_sec):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_sec)
    try:
        s.connect((ip, port))
        s.close()
        return (ip, port, True)
    except Exception:
        return (ip, port, False)

# Helper untuk mengirim DICOM C-ECHO
def verify_dicom_connection(host, port, calling_aet="ORTHANC_BRIDGE", called_aet="ANY-SCP", timeout=1.0):
    ae = AE(ae_title=calling_aet)
    ae.add_requested_context(Verification)
    ae.connection_timeout = timeout
    ae.acse_timeout = timeout
    ae.network_timeout = timeout
    ae.dimse_timeout = timeout
    assoc = ae.associate(host, port, ae_title=called_aet)
    
    remote_aet = None
    if hasattr(assoc, 'acceptor') and hasattr(assoc.acceptor, 'ae_title'):
        remote_aet = assoc.acceptor.ae_title
        if remote_aet:
            if isinstance(remote_aet, bytes):
                try:
                    remote_aet = remote_aet.decode('utf-8')
                except Exception:
                    pass
            remote_aet = str(remote_aet).strip()

    if assoc.is_established:
        try:
            status = assoc.send_c_echo()
            assoc.release()
            if status and status.Status == 0x0000:
                return True, "C-ECHO Sukses", remote_aet
            else:
                return False, f"C-ECHO Gagal (Status: {status.Status})", remote_aet
        except Exception as e:
            return False, f"C-ECHO Error: {str(e)}", remote_aet
    else:
        return False, "Koneksi Ditolak (Asosiasi Ditolak - Cek AE Title)", remote_aet

# View untuk menampilkan halaman DICOM scanner
@login_required
def dicom_scanner_view(request):
    devices = DicomDevice.objects.all()
    suggested_subnet = get_suggested_subnet()
    calling_aet = SystemConfig.get_val('DICOM_CALLING_AET', 'ORTHANC_BRIDGE')
    return render(request, 'dicom_scanner.html', {
        'devices': devices,
        'suggested_subnet': suggested_subnet,
        'calling_aet': calling_aet
    })

# API untuk scan subnet jaringan
@csrf_exempt
@login_required
@require_http_methods(["POST"])
def dicom_scan_api(request):
    try:
        # Parsing data request
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        subnet = str(data.get('subnet', '')).strip()
        ports_str = str(data.get('ports', '104,11112,4242')).strip()
        timeout_ms = int(data.get('timeout', '200'))

        # Parse daftar port
        ports = []
        for p in ports_str.split(','):
            try:
                ports.append(int(p.strip()))
            except ValueError:
                pass
        if not ports:
            ports = [104, 11112, 4242]

        timeout_sec = timeout_ms / 1000.0

        # Validasi format subnet (X.X.X)
        octets = subnet.split('.')
        if len(octets) != 3 or not all(o.isdigit() and 0 <= int(o) <= 255 for o in octets):
            return JsonResponse({"success": False, "message": "Format subnet tidak valid. Harus X.X.X (misal: 192.168.1)"})

        # Susun daftar target IP & Port
        targets = []
        if subnet.startswith("127.0."):
            # Jika memindai localhost/loopback, batasi hanya ke 127.0.0.1 untuk mencegah 254 duplikasi palsu
            for port in ports:
                targets.append(("127.0.0.1", port))
        else:
            for i in range(1, 255):
                ip = f"{subnet}.{i}"
                for port in ports:
                    targets.append((ip, port))

        results = []
        calling_aet = SystemConfig.get_val('DICOM_CALLING_AET', 'ORTHANC_BRIDGE')

        # Port scanning secara paralel menggunakan ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            future_to_target = {
                executor.submit(check_host_port, ip, port, timeout_sec): (ip, port)
                for ip, port in targets
            }
            for future in concurrent.futures.as_completed(future_to_target):
                ip, port = future_to_target[future]
                try:
                    ip, port, is_open = future.result()
                    if is_open:
                        # Jika TCP port terbuka, coba C-ECHO secara singkat
                        is_dicom, detail, remote_aet = verify_dicom_connection(
                            ip, port, calling_aet=calling_aet, called_aet="ANY-SCP", timeout=1.0
                        )
                        is_registered = DicomDevice.objects.filter(host=ip, port=port).exists()
                        results.append({
                            "ip": ip,
                            "port": port,
                            "dicom_verified": is_dicom,
                            "status": "online" if is_dicom else "unverified",
                            "status_display": "Online" if is_dicom else "TCP Terbuka",
                            "detail": detail,
                            "ae_title": remote_aet or "ANY-SCP",
                            "registered": is_registered
                        })
                except Exception:
                    pass

        # Urutkan berdasarkan octet terakhir IP
        results.sort(key=lambda x: [int(o) for o in x['ip'].split('.')])
        return JsonResponse({"success": True, "devices": results})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

# API untuk verifikasi konektivitas DICOM perangkat
@csrf_exempt
@login_required
@require_http_methods(["POST"])
def dicom_verify_api(request):
    try:
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        host = data.get('host')
        port = int(data.get('port', 104))
        device_id = data.get('device_id')
        called_aet = data.get('ae_title') or "ANY-SCP"
        calling_aet = SystemConfig.get_val('DICOM_CALLING_AET', 'ORTHANC_BRIDGE')

        if not host:
            return JsonResponse({"success": False, "message": "Host IP harus diisi."})

        # Jalankan C-ECHO
        success, detail, remote_aet = verify_dicom_connection(host, port, calling_aet=calling_aet, called_aet=called_aet, timeout=2.0)

        # Update database jika id perangkat terdaftar disertakan
        status_val = "online" if success else "offline"
        if device_id:
            try:
                device = DicomDevice.objects.get(id=device_id)
                device.status = status_val
                device.last_checked = timezone.now()
                if success and remote_aet:
                    device.ae_title = remote_aet
                device.save()
            except DicomDevice.DoesNotExist:
                pass

        return JsonResponse({
            "success": success,
            "status": status_val,
            "status_display": "Online" if success else "Offline",
            "message": detail
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

# API untuk mendaftarkan perangkat DICOM baru
@csrf_exempt
@login_required
@require_http_methods(["POST"])
def dicom_register_api(request):
    try:
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        name = str(data.get('name', '')).strip()
        host = str(data.get('host', '')).strip()
        port = int(data.get('port', 104))
        ae_title = str(data.get('ae_title', '')).strip()
        description = str(data.get('description', '')).strip()

        if not name or not host:
            return JsonResponse({"success": False, "message": "Nama dan Host IP wajib diisi."})

        # Cek apakah sudah terdaftar
        device, created = DicomDevice.objects.get_or_create(
            host=host,
            port=port,
            defaults={
                'name': name,
                'ae_title': ae_title,
                'description': description,
                'status': 'unverified'
            }
        )

        if not created:
            # Update data jika sudah ada
            device.name = name
            device.ae_title = ae_title
            device.description = description
            device.save()

        # Jalankan C-ECHO verifikasi secara langsung agar status terupdate
        calling_aet = SystemConfig.get_val('DICOM_CALLING_AET', 'ORTHANC_BRIDGE')
        called_aet = ae_title or "ANY-SCP"
        success, detail, remote_aet = verify_dicom_connection(host, port, calling_aet=calling_aet, called_aet=called_aet, timeout=1.5)
        
        if success and remote_aet and not device.ae_title:
            device.ae_title = remote_aet
            
        device.status = "online" if success else "unverified"
        device.last_checked = timezone.now()
        device.save()

        msg = "Perangkat DICOM berhasil didaftarkan." if created else "Perangkat DICOM berhasil diperbarui."
        if success:
            msg += " Koneksi C-ECHO berhasil."
        else:
            msg += f" Namun C-ECHO belum berhasil: {detail}"

        return JsonResponse({
            "success": True,
            "message": msg,
            "device": {
                "id": str(device.id),
                "name": device.name,
                "host": device.host,
                "port": device.port,
                "ae_title": device.ae_title,
                "status": device.status,
                "status_display": "Online" if device.status == "online" else "Offline" if device.status == "offline" else "Unverified"
            }
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

# API untuk menghapus perangkat DICOM
@csrf_exempt
@login_required
@require_http_methods(["POST"])
def dicom_delete_api(request):
    try:
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        device_id = data.get('id')
        if not device_id:
            return JsonResponse({"success": False, "message": "ID perangkat tidak valid."})

        try:
            device = DicomDevice.objects.get(id=device_id)
            device.delete()
            return JsonResponse({"success": True, "message": "Perangkat DICOM berhasil dihapus."})
        except DicomDevice.DoesNotExist:
            return JsonResponse({"success": False, "message": "Perangkat tidak ditemukan."})

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

# View untuk menampilkan halaman DICOM router
@login_required
def dicom_router_view(request):
    """Halaman utama router DICOM, memuat aturan routing otomatis"""
    devices = DicomDevice.objects.all()
    rules = RoutingRule.objects.all()
    routing_logs = RoutingLog.objects.all()[:15]
    calling_aet = SystemConfig.get_val('DICOM_CALLING_AET', 'ORTHANC_BRIDGE')
    
    return render(request, 'dicom_router.html', {
        'devices': devices,
        'rules': rules,
        'routing_logs': routing_logs,
        'calling_aet': calling_aet
    })

# View untuk halaman Scheduled Backup (dipisahkan dari DICOM Router)
@login_required
def scheduled_backup_view(request):
    """Halaman manajemen jadwal backup/sinkronisasi PACS"""
    devices = DicomDevice.objects.all()
    schedules = SyncSchedule.objects.all()
    sync_logs = SyncLog.objects.all()[:15]
    
    return render(request, 'scheduled_backup.html', {
        'devices': devices,
        'schedules': schedules,
        'sync_logs': sync_logs,
    })


# ─── API OTOMASI & PERUTEAN DICOM ──────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def dicom_modify_api(request, study_id):
    """
    API AJAX: Memodifikasi tag atau menganonimkan studi DICOM di Orthanc local.
    """
    try:
        data = json.loads(request.body)
        action_type = data.get('action') # 'anonymize' atau 'modify'
        
        url  = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
        user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
        pw   = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
        clean_url = url.rstrip('/')

        payload = {}
        if action_type == 'anonymize':
            # Aturan standard anonimisasi DICOM
            payload = {
                "Keep": ["StationName", "SeriesDescription", "ProtocolName"],
                "DicomVersion": "2021b"
            }
            endpoint = f"{clean_url}/studies/{study_id}/anonymize"
        elif action_type == 'modify':
            replace_tags = data.get('replace', {})
            remove_tags = data.get('remove', [])
            payload = {
                "Replace": replace_tags,
                "Remove": remove_tags,
                "Force": True
            }
            endpoint = f"{clean_url}/studies/{study_id}/modify"
        else:
            return JsonResponse({"success": False, "message": "Aksi tidak didukung."}, status=400)

        resp = requests.post(endpoint, auth=(user, pw), json=payload, timeout=30)
        if resp.status_code != 200:
            return JsonResponse({"success": False, "message": f"Orthanc Error: {resp.text}"}, status=500)
            
        result = resp.json()
        new_study_id = result.get('ID')

        return JsonResponse({
            "success": True,
            "message": f"Studi berhasil di-{action_type}! Studi baru tersimpan dengan ID: {new_study_id}",
            "new_study_id": new_study_id
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def routing_rules_api(request):
    """
    API AJAX: CRUD Aturan Perutean Otomatis (Auto-Routing Rules).
    """
    if request.method == "GET":
        rules = list(RoutingRule.objects.all().values(
            'id', 'name', 'modality', 'patient_id_prefix', 'study_desc_contains', 'target_device__name', 'is_active'
        ))
        return JsonResponse({"success": True, "rules": rules})

    # POST (Create / Toggle / Delete)
    try:
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'create':
            name = data.get('name')
            modality = data.get('modality', '').upper().strip()
            patient_id_prefix = data.get('patient_id_prefix', '').strip()
            study_desc_contains = data.get('study_desc_contains', '').strip()
            device_id = data.get('device_id')

            if not name or not device_id:
                return JsonResponse({"success": False, "message": "Nama dan Node Tujuan wajib diisi."}, status=400)

            device = DicomDevice.objects.get(id=device_id)
            rule = RoutingRule.objects.create(
                name=name,
                modality=modality,
                patient_id_prefix=patient_id_prefix,
                study_desc_contains=study_desc_contains,
                target_device=device
            )
            return JsonResponse({"success": True, "message": f"Aturan '{rule.name}' berhasil dibuat!"})

        elif action == 'toggle':
            rule_id = data.get('rule_id')
            rule = RoutingRule.objects.get(id=rule_id)
            rule.is_active = not rule.is_active
            rule.save()
            return JsonResponse({"success": True, "message": f"Status aturan '{rule.name}' berhasil diubah."})

        elif action == 'delete':
            rule_id = data.get('rule_id')
            rule = RoutingRule.objects.get(id=rule_id)
            rule.delete()
            return JsonResponse({"success": True, "message": "Aturan perutean berhasil dihapus."})

        return JsonResponse({"success": False, "message": "Aksi tidak valid."}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def sync_schedules_api(request):
    """
    API AJAX: CRUD Penjadwalan Backup / Sinkronisasi PACS.
    """
    if request.method == "GET":
        schedules = list(SyncSchedule.objects.all().values(
            'id', 'name', 'target_device__name', 'frequency', 'last_run', 'next_run', 'is_active'
        ))
        return JsonResponse({"success": True, "schedules": schedules})

    # POST (Create / Toggle / Delete)
    try:
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'create':
            name = data.get('name')
            device_id = data.get('device_id')
            frequency = data.get('frequency', 'daily')

            if not name or not device_id:
                return JsonResponse({"success": False, "message": "Nama dan Node Tujuan wajib diisi."}, status=400)

            device = DicomDevice.objects.get(id=device_id)
            schedule = SyncSchedule.objects.create(
                name=name,
                target_device=device,
                frequency=frequency
            )
            return JsonResponse({"success": True, "message": f"Jadwal '{schedule.name}' berhasil ditambahkan!"})

        elif action == 'toggle':
            sched_id = data.get('schedule_id')
            schedule = SyncSchedule.objects.get(id=sched_id)
            schedule.is_active = not schedule.is_active
            schedule.save()
            return JsonResponse({"success": True, "message": f"Status jadwal '{schedule.name}' berhasil diubah."})

        elif action == 'delete':
            sched_id = data.get('schedule_id')
            schedule = SyncSchedule.objects.get(id=sched_id)
            schedule.delete()
            return JsonResponse({"success": True, "message": "Jadwal pencadangan berhasil dihapus."})

        return JsonResponse({"success": False, "message": "Aksi tidak valid."}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def routing_logs_api(request):
    """
    API AJAX: Membaca log perutean otomatis terbaru.
    """
    logs = list(RoutingLog.objects.all()[:15].values(
        'id', 'patient_name', 'modality', 'target_device_name', 'status', 'error_message', 'created_at'
    ))
    return JsonResponse({"success": True, "logs": logs})


@login_required
@require_http_methods(["GET"])
def sync_logs_api(request):
    """
    API AJAX: Membaca log sinkronisasi backup terbaru.
    """
    logs = list(SyncLog.objects.all()[:15].values(
        'id', 'schedule__name', 'total_studies', 'status', 'error_message', 'created_at'
    ))
    return JsonResponse({"success": True, "logs": logs})


@login_required
@require_http_methods(["POST"])
def sync_single_device_to_orthanc(request, device_id):
    """Mendaftarkan satu DicomDevice ke Orthanc sebagai modality."""
    url  = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
    user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
    pw   = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')

    try:
        device = DicomDevice.objects.get(id=device_id)
    except DicomDevice.DoesNotExist:
        return JsonResponse({"success": False, "message": "Perangkat tidak ditemukan."}, status=404)

    symbolic_name = f"device_{device.id.hex}"
    payload = {
        "AET":        device.ae_title or "UNKNOWN",
        "Host":       device.host,
        "Port":       int(device.port),
        "Manufacturer": "Generic",
        "AllowEcho":  True,
        "AllowStore": True,
    }
    try:
        r = requests.put(
            f"{url.rstrip('/')}/modalities/{symbolic_name}",
            auth=(user, pw), json=payload, timeout=5
        )
        if r.status_code in (200, 201):
            return JsonResponse({"success": True, "message": f"'{device.name}' berhasil disinkronkan ke Orthanc."})
        return JsonResponse({"success": False, "message": f"Orthanc error {r.status_code}: {r.text}"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def sync_modality_to_local(request):
    """Menyimpan modality dari Orthanc ke tabel DicomDevice lokal."""
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"success": False, "message": "Body tidak valid."}, status=400)

    name = str(data.get("name", "")).strip()
    aet  = str(data.get("aet", "")).strip()
    host = str(data.get("host", "")).strip()
    port = int(data.get("port", 104))
    mfr  = str(data.get("manufacturer", "Generic")).strip()

    if not host:
        return JsonResponse({"success": False, "message": "Host IP tidak tersedia pada modality ini."}, status=400)

    device, created = DicomDevice.objects.get_or_create(
        host=host, port=port,
        defaults={
            "name":        name,
            "ae_title":    aet,
            "description": f"Disinkronkan dari Orthanc modality '{name}'. Manufacturer: {mfr}",
            "status":      "unverified",
        }
    )
    if not created:
        device.name     = name
        device.ae_title = aet
        device.save()

    action = "ditambahkan" if created else "diperbarui"
    return JsonResponse({"success": True, "message": f"Modality '{name}' berhasil {action} ke DICOM Nodes lokal."})


@login_required
@require_http_methods(["POST"])
def sync_modalities_to_orthanc(request):
    """Mendaftarkan semua DicomDevice ke Orthanc sebagai modalities via REST API."""
    url  = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
    user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
    pw   = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
    clean_url = url.rstrip('/')

    devices = DicomDevice.objects.all()
    success_count = 0
    failed = []

    for device in devices:
        symbolic_name = f"device_{device.id.hex}"
        payload = {
            "AET": device.ae_title or "UNKNOWN",
            "Host": device.host,
            "Port": int(device.port),
            "Manufacturer": "Generic",
            "AllowEcho": True,
            "AllowStore": True,
        }
        try:
            r = requests.put(
                f"{clean_url}/modalities/{symbolic_name}",
                auth=(user, pw),
                json=payload,
                timeout=5
            )
            if r.status_code in (200, 201):
                success_count += 1
            else:
                failed.append(f"{device.name} (HTTP {r.status_code})")
        except Exception as e:
            failed.append(f"{device.name} ({str(e)})")

    if failed:
        return JsonResponse({
            "success": False,
            "message": f"{success_count} berhasil, {len(failed)} gagal: {', '.join(failed)}"
        })
    return JsonResponse({
        "success": True,
        "message": f"Berhasil sinkronisasi {success_count} perangkat ke Orthanc."
    })


@login_required
def orthanc_modalities_api(request):
    """CRUD modalities langsung ke Orthanc REST API."""
    url  = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
    user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
    pw   = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
    clean_url = url.rstrip('/')

    if request.method == "GET":
        try:
            r = requests.get(f"{clean_url}/modalities?expand", auth=(user, pw), timeout=5)
            if r.status_code == 200:
                raw = r.json()
                modalities = [
                    {"name": name, **data}
                    for name, data in raw.items()
                ]
                return JsonResponse({"success": True, "modalities": modalities})
            return JsonResponse({"success": False, "message": f"Orthanc merespon {r.status_code}"}, status=502)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"success": False, "message": "Body tidak valid."}, status=400)

    action = data.get("action")

    if action in ("create", "update"):
        name = str(data.get("name", "")).strip()
        if not name:
            return JsonResponse({"success": False, "message": "Nama modality wajib diisi."}, status=400)
        payload = {
            "AET":          str(data.get("aet", "")).strip() or name.upper(),
            "Host":         str(data.get("host", "")).strip(),
            "Port":         int(data.get("port", 104)),
            "Manufacturer": str(data.get("manufacturer", "Generic")).strip(),
            "AllowEcho":    bool(data.get("allow_echo", True)),
            "AllowStore":   bool(data.get("allow_store", True)),
        }
        if not payload["Host"]:
            return JsonResponse({"success": False, "message": "Host IP wajib diisi."}, status=400)
        try:
            r = requests.put(
                f"{clean_url}/modalities/{name}",
                auth=(user, pw), json=payload, timeout=5
            )
            if r.status_code in (200, 201):
                return JsonResponse({"success": True, "message": f"Modality '{name}' berhasil disimpan."})
            return JsonResponse({"success": False, "message": f"Orthanc error: {r.text}"}, status=500)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)

    if action == "delete":
        name = str(data.get("name", "")).strip()
        if not name:
            return JsonResponse({"success": False, "message": "Nama modality wajib diisi."}, status=400)
        try:
            r = requests.delete(f"{clean_url}/modalities/{name}", auth=(user, pw), timeout=5)
            if r.status_code in (200, 204):
                return JsonResponse({"success": True, "message": f"Modality '{name}' berhasil dihapus."})
            return JsonResponse({"success": False, "message": f"Orthanc error: {r.text}"}, status=500)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)

    return JsonResponse({"success": False, "message": "Aksi tidak valid."}, status=400)


def error_404_view(request, exception):
    return render(request, '404.html', status=404)

def error_500_view(request):
    return render(request, '500.html', status=500)


@login_required
@require_http_methods(["POST"])
def upload_logo_view(request):
    """Mengupload logo/icon kustom untuk menggantikan logo default aplikasi."""
    logo_file = request.FILES.get('logo')
    if not logo_file:
        messages.error(request, "Tidak ada file yang dipilih.")
        return redirect('configuration_page')

    allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/x-icon', 'image/vnd.microsoft.icon']
    if logo_file.content_type not in allowed_types:
        messages.error(request, "Format file tidak didukung. Gunakan PNG, JPG, SVG, atau ICO.")
        return redirect('configuration_page')

    max_size = 2 * 1024 * 1024  # 2 MB
    if logo_file.size > max_size:
        messages.error(request, "Ukuran file maksimal 2MB.")
        return redirect('configuration_page')

    media_dir = os.path.join(settings.MEDIA_ROOT, 'branding')
    os.makedirs(media_dir, exist_ok=True)

    ext = os.path.splitext(logo_file.name)[1].lower() or '.png'
    dest_path = os.path.join(media_dir, f'logo-icon{ext}')

    # Hapus file logo lama jika ada
    for f in os.listdir(media_dir):
        if f.startswith('logo-icon'):
            os.remove(os.path.join(media_dir, f))

    with open(dest_path, 'wb+') as destination:
        for chunk in logo_file.chunks():
            destination.write(chunk)

    SystemConfig.objects.update_or_create(
        key='CUSTOM_LOGO_PATH',
        defaults={'value': f'branding/logo-icon{ext}', 'description': 'Path logo kustom relatif dari MEDIA_ROOT'}
    )
    from django.core.cache import cache
    cache.delete('ctx_logo_url')

    messages.success(request, "Logo berhasil diperbarui.")
    return redirect('configuration_page')


@login_required
@require_http_methods(["POST"])
def reset_logo_view(request):
    """Menghapus logo kustom dan mengembalikan ke logo default."""
    try:
        config = SystemConfig.objects.get(key='CUSTOM_LOGO_PATH')
        media_dir = os.path.join(settings.MEDIA_ROOT, 'branding')
        file_path = os.path.join(settings.MEDIA_ROOT, config.value)
        if os.path.exists(file_path):
            os.remove(file_path)
        config.delete()
    except SystemConfig.DoesNotExist:
        pass

    from django.core.cache import cache
    cache.delete('ctx_logo_url')

    messages.success(request, "Logo berhasil direset ke default.")
    return redirect('configuration_page')
