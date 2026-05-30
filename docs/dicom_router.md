# DICOM Router & Auto-Routing Rules

Fitur **DICOM Router** menyediakan panel terpusat untuk mengelola perangkat target DICOM (Nodes) dan aturan perutean otomatis (Auto-Routing) secara real-time.

## Fitur Utama

1. **DICOM Nodes Management**:
   * Pendaftaran, pengubahan, dan penghapusan perangkat DICOM secara manual.
   * Uji konektivitas C-ECHO (Ping) asinkron dengan indikator status online/offline visual yang modern.
2. **Auto-Routing Engine**:
   * Konfigurasi aturan perutean otomatis berdasarkan filter Modality, prefiks Patient ID, dan teks deskripsi studi.
   * Dashboard log aktivitas perutean real-time untuk audit transaksi transmisi studi DICOM ke workstation tujuan.

## Detail Implementasi Komponen

* **Backend View & API**: 
  * `dicom_router_view`: Merender template `dicom_router.html`.
  * `/api/routing-rules/` (`routing_rules_api`): Endpoint CRUD aturan routing (create, toggle status, delete).
  * `/api/routing-logs/` (`routing_logs_api`): Endpoint log audit perutean otomatis.
* **Background Worker**: `run_routing_engine.py` (Command CLI Django polling berkala setiap 10 detik untuk mencocokkan studi baru di Orthanc PACS dan melakukan transmisi C-STORE otomatis).

---

## Verifikasi Teknis

* Validasi integritas kode: `python manage.py check` (0 isu terdeteksi).
