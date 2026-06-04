import os
import time
import json
import requests
import traceback
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from bridge.models import SystemConfig, SyncSchedule, SyncLog, DicomDevice

class Command(BaseCommand):
    help = "Menjalankan penjadwal pencadangan otomatis (Scheduled Backup) studi DICOM"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("[START] PACS Backup & Sync Scheduler berjalan..."))

        # Jalankan loop polling setiap 60 detik (1 menit) untuk memeriksa jadwal aktif
        while True:
            try:
                # Muat ulang konfigurasi Orthanc
                url  = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
                user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
                pw   = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
                clean_url = url.rstrip('/')

                now = timezone.now()
                active_schedules = SyncSchedule.objects.filter(is_active=True)

                for schedule in active_schedules:
                    run_needed  = False
                    local_now   = now.astimezone()

                    if not schedule.last_run:
                        run_needed = True
                    else:
                        elapsed = now - schedule.last_run
                        if schedule.frequency == 'hourly':
                            run_needed = elapsed >= timedelta(hours=1)
                        elif schedule.frequency == 'daily':
                            # Jalankan jika sudah lewat 23 jam DAN saat ini >= jam terjadwal
                            past_threshold = elapsed >= timedelta(hours=23)
                            at_scheduled_time = (
                                local_now.hour > schedule.run_hour or
                                (local_now.hour == schedule.run_hour and local_now.minute >= schedule.run_minute)
                            )
                            run_needed = past_threshold and at_scheduled_time
                        elif schedule.frequency == 'weekly':
                            past_threshold = elapsed >= timedelta(days=6, hours=23)
                            at_scheduled_time = (
                                local_now.hour > schedule.run_hour or
                                (local_now.hour == schedule.run_hour and local_now.minute >= schedule.run_minute)
                            )
                            run_needed = past_threshold and at_scheduled_time

                    if not run_needed:
                        continue

                    self.stdout.write(self.style.SUCCESS(f"[RUN] Memulai jadwal backup: '{schedule.name}' -> {schedule.target_device.name}"))
                    
                    # 1. Hitung Rentang Tanggal DICOM berdasarkan Frekuensi
                    today_str = datetime.now().strftime("%Y%m%d")
                    if schedule.frequency == 'hourly':
                        # Hanya studi hari ini
                        date_range = today_str
                    elif schedule.frequency == 'daily':
                        # Studi kemarin s/d hari ini
                        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
                        date_range = f"{yesterday_str}-{today_str}"
                    else:
                        # Mingguan: studi 7 hari terakhir
                        last_week_str = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
                        date_range = f"{last_week_str}-{today_str}"

                    # 2. Cari studi di Orthanc menggunakan /tools/find dengan filter tanggal & modality
                    find_query = {"StudyDate": date_range}
                    if schedule.modality_filter:
                        modalities = [m.strip() for m in schedule.modality_filter.split(',') if m.strip()]
                        if len(modalities) == 1:
                            find_query["ModalitiesInStudy"] = modalities[0]

                    find_payload = {"Level": "Study", "Query": find_query}

                    try:
                        find_resp = requests.post(f"{clean_url}/tools/find", auth=(user, pw), json=find_payload, timeout=30)
                        if find_resp.status_code != 200:
                            raise Exception(f"Gagal melakukan pencarian studi di Orthanc: {find_resp.text}")

                        study_ids = find_resp.json()
                        total_studies = len(study_ids)
                        self.stdout.write(f"     Ditemukan {total_studies} studi dalam rentang tanggal {date_range} untuk dibackup.")

                        if total_studies == 0:
                            # Catat log sukses kosong
                            SyncLog.objects.create(
                                schedule=schedule,
                                total_studies=0,
                                status="Success",
                                error_message="Tidak ada studi baru untuk dibackup dalam rentang waktu."
                            )
                            schedule.last_run = now
                            schedule.save()
                            continue

                        # Registrasikan target device di Orthanc dinamis
                        device = schedule.target_device
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
                            raise Exception(f"Registrasi target backup di Orthanc gagal: {put_resp.text}")

                        success_count = 0
                        failed_count = 0
                        errors_summary = []

                        # 3. Lakukan C-STORE push ke Orthanc secara berurutan untuk setiap studi
                        for study_id in study_ids:
                            try:
                                post_resp = requests.post(
                                    f"{clean_url}/modalities/{modality_symbolic_name}/store",
                                    auth=(user, pw),
                                    json=[study_id],
                                    timeout=120
                                )
                                
                                if post_resp.status_code != 200:
                                    raise Exception(f"Gagal transfer: {post_resp.text}")

                                store_res = post_resp.json()
                                failed_inst = store_res.get('FailedInstancesCount', 0)
                                if failed_inst > 0:
                                    raise Exception(f"Selesai dengan kegagalan: {failed_inst} instance gagal dikirim.")
                                
                                success_count += 1
                            except Exception as ex:
                                failed_count += 1
                                errors_summary.append(f"Study ID {study_id}: {str(ex)}")

                        # 4. Catat Log Aktivitas Backup
                        status_summary = "Success" if failed_count == 0 else ("Partial" if success_count > 0 else "Failed")
                        error_txt = "\n".join(errors_summary) if errors_summary else None

                        SyncLog.objects.create(
                            schedule=schedule,
                            total_studies=success_count,
                            status=status_summary,
                            error_message=error_txt
                        )

                        # Perbarui jadwal last run
                        schedule.last_run = now
                        schedule.save()

                        self.stdout.write(self.style.SUCCESS(f"     [OK] Jadwal '{schedule.name}' selesai. Berhasil: {success_count}, Gagal: {failed_count}"))

                    except Exception as sched_ex:
                        err_msg = str(sched_ex)
                        self.stdout.write(self.style.ERROR(f"     [FAIL] Jadwal '{schedule.name}' gagal: {err_msg}"))
                        SyncLog.objects.create(
                            schedule=schedule,
                            total_studies=0,
                            status="Failed",
                            error_message=err_msg
                        )
                        # Upayakan untuk tetap perbarui last run agar tidak terus berulang-ulang di iterasi berikutnya
                        schedule.last_run = now
                        schedule.save()

            except Exception as system_ex:
                self.stdout.write(self.style.ERROR(f"[SYSTEM ERR] Kesalahan loop backup: {str(system_ex)}"))
                traceback.print_exc()

            # Periksa jadwal setiap 1 menit
            time.sleep(60)
