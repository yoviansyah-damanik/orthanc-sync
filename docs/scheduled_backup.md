# Scheduled PACS Backup & Sync

Fitur **Scheduled Backup** menyediakan antarmuka mandiri untuk mengonfigurasi dan memantau pencadangan studi DICOM secara terjadwal dari Orthanc PACS ke node cadangan eksternal.

## Fitur Utama

1. **Jadwal Pencadangan Terjadwal**:
   * Konfigurasi jadwal sinkronisasi berkala dengan frekuensi: Setiap Jam (Hourly), Setiap Hari (Daily), atau Setiap Minggu (Weekly).
   * Pengaktifan, penonaktifan, dan penghapusan jadwal sinkronisasi secara dinamis.
2. **Audit & Log Sinkronisasi**:
   * Riwayat pencadangan lengkap mencakup tanggal eksekusi, nama jadwal pemicu, jumlah total studi yang dicadangkan, dan status keberhasilan (Success, Partial, Failed).
   * Tombol refresh asinkron untuk memuat riwayat log terbaru.

## Detail Implementasi Komponen

* **Backend View & API**:
  * `scheduled_backup_view`: Merender template `scheduled_backup.html`.
  * `/api/sync-schedules/` (`sync_schedules_api`): Endpoint CRUD jadwal sinkronisasi.
  * `/api/sync-logs/` (`sync_logs_api`): Endpoint riwayat log audit backup.
* **Background Worker**: `run_backup_scheduler.py` (Command CLI Django memproses pencadangan terjadwal berkala ke node tujuan).

---

## Verifikasi Teknis

* Validasi integritas kode: `python manage.py check` (0 isu terdeteksi).
