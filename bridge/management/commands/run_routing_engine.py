import os
import time
import json
import requests
import traceback
from django.core.management.base import BaseCommand
from django.conf import settings
from bridge.models import SystemConfig, RoutingRule, RoutingLog, DicomDevice

class Command(BaseCommand):
    help = "Menjalankan mesin perutean DICOM otomatis berdasarkan perubahan studi Orthanc"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("[START] Auto-Routing Rules Engine berjalan..."))
        
        # Inisialisasi index terakhir dari SystemConfig
        last_change_key = "LAST_ROUTED_CHANGE_INDEX"
        last_index_str = SystemConfig.get_val(last_change_key, "0")
        try:
            last_index = int(last_index_str)
        except ValueError:
            last_index = 0

        self.stdout.write(f"Index perubahan terakhir: {last_index}")

        # Jalankan loop polling secara berkala
        while True:
            try:
                # Muat ulang konfigurasi Orthanc terbaru dari database
                url  = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
                user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
                pw   = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
                clean_url = url.rstrip('/')

                # 1. Tarik daftar perubahan (changes) terbaru dari Orthanc
                # Limit 50 perubahan per iterasi agar tidak kelebihan beban memori
                changes_endpoint = f"{clean_url}/changes?last={last_index}&limit=50"
                
                try:
                    resp = requests.get(changes_endpoint, auth=(user, pw), timeout=10)
                except requests.exceptions.RequestException as e:
                    self.stdout.write(self.style.WARNING(f"[ERR] Koneksi ke Orthanc gagal: {str(e)}. Coba lagi dalam 15 detik..."))
                    time.sleep(15)
                    continue

                if resp.status_code != 200:
                    self.stdout.write(self.style.ERROR(f"[ERR] Gagal mengambil data perubahan dari Orthanc: {resp.text}"))
                    time.sleep(10)
                    continue

                changes_data = resp.json()
                changes = changes_data.get('Changes', [])
                last_index = changes_data.get('Last', last_index)

                # Simpan index perubahan terakhir ke database
                config_obj, _ = SystemConfig.objects.get_or_create(key=last_change_key)
                config_obj.value = str(last_index)
                config_obj.save()

                for change in changes:
                    # Kita hanya tertarik pada studi yang statusnya telah stabil (selesai diupload semua instance)
                    if change.get('Type') != 'StableStudy':
                        continue

                    study_id = change.get('ID')
                    self.stdout.write(f"Mendeteksi studi stabil baru: ID {study_id}")
                    
                    # 2. Ambil detail informasi studi dari Orthanc
                    study_endpoint = f"{clean_url}/studies/{study_id}"
                    study_resp = requests.get(study_endpoint, auth=(user, pw), timeout=10)
                    if study_resp.status_code != 200:
                        self.stdout.write(self.style.ERROR(f"     Gagal mengambil info studi: {study_resp.text}"))
                        continue

                    study_info = study_resp.json()
                    
                    # Ekstraksi metadata utama DICOM
                    dicom_patient_tags = study_info.get('PatientMainDicomTags', {})
                    dicom_study_tags = study_info.get('MainDicomTags', {})
                    
                    patient_id = dicom_patient_tags.get('PatientID', '').strip()
                    patient_name = dicom_patient_tags.get('PatientName', '').strip()
                    study_desc = dicom_study_tags.get('StudyDescription', '').strip()
                    
                    # Orthanc menyimpan daftar Modality di ModalitiesInStudy (list atau string tunggal)
                    modalities = study_info.get('ModalitiesInStudy', [])
                    if not isinstance(modalities, list):
                        modalities = [modalities] if modalities else []
                    
                    # Pastikan modality tidak kosong, fallback ke cek series jika kosong
                    if not modalities:
                        series_list = study_info.get('Series', [])
                        if series_list:
                            # Cek modalitas pada series pertama
                            first_series_resp = requests.get(f"{clean_url}/series/{series_list[0]}", auth=(user, pw), timeout=5)
                            if first_series_resp.status_code == 200:
                                s_info = first_series_resp.json()
                                s_modality = s_info.get('MainDicomTags', {}).get('Modality')
                                if s_modality:
                                    modalities = [s_modality]

                    modality_str = ", ".join(modalities)
                    self.stdout.write(f"     Pasien: {patient_name} ({patient_id}), Modality: {modality_str}, Deskripsi: {study_desc}")

                    # 3. Cari dan cocokkan dengan aturan perutean (RoutingRule) aktif
                    active_rules = RoutingRule.objects.filter(is_active=True)
                    
                    for rule in active_rules:
                        matched = True

                        # Filter Modality
                        if rule.modality:
                            if not any(m.upper() == rule.modality.upper() for m in modalities):
                                matched = False

                        # Filter Prefiks Patient ID
                        if matched and rule.patient_id_prefix:
                            if not patient_id.startswith(rule.patient_id_prefix):
                                matched = False

                        # Filter Deskripsi Studi (Case Insensitive)
                        if matched and rule.study_desc_contains:
                            if rule.study_desc_contains.lower() not in study_desc.lower():
                                matched = False

                        # Jika semua kriteria terpenuhi -> Lakukan perutean!
                        if matched:
                            device = rule.target_device
                            self.stdout.write(self.style.SUCCESS(f"     [MATCH] Aturan '{rule.name}' cocok! Mengirim ke: {device.name} ({device.ae_title})"))
                            
                            # Jalankan registrasi node tujuan secara dinamis di Orthanc
                            modality_symbolic_name = f"device_{device.id.hex}"
                            modality_payload = {
                                "AET": device.ae_title,
                                "Host": device.host,
                                "Port": int(device.port),
                                "Manufacturer": "Generic",
                                "AllowEcho": True,
                                "AllowStore": True
                            }

                            try:
                                # Registrasikan remote node
                                put_resp = requests.put(
                                    f"{clean_url}/modalities/{modality_symbolic_name}",
                                    auth=(user, pw),
                                    json=modality_payload,
                                    timeout=10
                                )

                                if put_resp.status_code not in (200, 201):
                                    raise Exception(f"Registrasi node tujuan di Orthanc gagal: {put_resp.text}")

                                # Kirim perintah C-STORE push ke Orthanc
                                post_resp = requests.post(
                                    f"{clean_url}/modalities/{modality_symbolic_name}/store",
                                    auth=(user, pw),
                                    json=[study_id],
                                    timeout=120
                                )

                                if post_resp.status_code != 200:
                                    raise Exception(f"C-STORE transfer gagal: {post_resp.text}")

                                store_result = post_resp.json()
                                failed_count = store_result.get('FailedInstancesCount', 0)

                                if failed_count > 0:
                                    raise Exception(f"Selesai dengan error: {failed_count} instance gagal dikirim.")

                                # Catat log keberhasilan
                                RoutingLog.objects.create(
                                    rule=rule,
                                    study_id=study_id,
                                    patient_name=patient_name,
                                    modality=modality_str,
                                    target_device_name=device.name,
                                    status="Success"
                                )
                                self.stdout.write(self.style.SUCCESS(f"     [OK] Studi berhasil dirutekan ke {device.name}."))

                            except Exception as ex:
                                error_msg = str(ex)
                                self.stdout.write(self.style.ERROR(f"     [FAIL] Gagal merutekan studi: {error_msg}"))
                                # Catat log kegagalan
                                RoutingLog.objects.create(
                                    rule=rule,
                                    study_id=study_id,
                                    patient_name=patient_name,
                                    modality=modality_str,
                                    target_device_name=device.name,
                                    status="Failed",
                                    error_message=error_msg
                                )

            except Exception as main_ex:
                self.stdout.write(self.style.ERROR(f"[SYSTEM ERR] Kesalahan pada loop utama: {str(main_ex)}"))
                traceback.print_exc()

            # Polling berkala setiap 10 detik agar hemat daya dan responsif
            time.sleep(10)
