# All Studies & PACS Browser

Fitur **All Studies** (Daftar Study) menyediakan panel interaktif berkelas premium untuk menelusuri, mencari, dan melihat rincian metadata medis (series & instances) dari seluruh data study DICOM yang tersimpan secara lokal di server PACS Orthanc secara asinkron.

## Fitur Utama

1. **Statistik Dinamis (Stat Cards)**:
   * Menampilkan ringkasan visual real-time seperti total study, jumlah study hari ini, jumlah modality aktif, dan total series DICOM yang dikalkulasi langsung di sisi klien secara asinkron.
2. **Pencarian Cepat dengan Debounce**:
   * Input pencarian pintar yang memicu query pencarian ke server PACS Orthanc via AJAX endpoint. Dilengkapi dengan debounce 300ms untuk mencegah penimbunan request berlebih ke server.
3. **Animated Loading Skeleton & Empty State**:
   * Selama memuat data, tabel menampilkan baris animasi pembuat kerangka (skeleton) abu-abu yang sangat halus untuk memberikan impresi performa secepat kilat.
   * Dilengkapi penanganan visual saat data kosong dengan SVG ilustratif yang elegan.
4. **Detail Study Modal Asinkron**:
   * Membuka rincian lengkap study dalam modal global dari `base.html`.
   * Menampilkan informasi detail pasien (ID, nama, lahir, gender) dan informasi studi (Accession, UID, waktu study, dokter, deskripsi).
   * Memuat tabel daftar seri DICOM lengkap dengan nomor seri, deskripsi, modality badge, jumlah instance, dan tombol cepat untuk menyalin Study Instance UID.

---

## Struktur Teknis

### 1. Backend Views & APIs (`bridge/views.py`)
* **`all_studies_view`**: Merender template `all_studies.html`.
* **`orthanc_studies_api`**: Endpoint AJAX GET `/api/orthanc-studies/` untuk melakukan query `/tools/find` ke Orthanc dengan dukungan filter nama pasien.
* **`orthanc_study_detail_api`**: Endpoint AJAX GET `/api/orthanc-studies/<study_id>/` untuk memuat rincian terperinci suatu study beserta daftar series dan jumlah instance-nya.

### 2. URL Routes (`config/urls.py`)
* `/all-studies/` -> `all_studies_page`
* `/api/orthanc-studies/` -> `orthanc_studies_api`
* `/api/orthanc-studies/<str:study_id>/` -> `orthanc_study_detail_api`

### 3. Sidebar Navigation (`bridge/context_processors.py`)
* Menambahkan item menu **Daftar Study** di bawah kelompok **Manajemen Data** dengan ikon daftar/list.

---

## Verifikasi Teknis

Aplikasi telah berhasil lolos uji integritas Django:
```bash
python manage.py check
```
Semua rute routing, handler views, dan binding template terintegrasi secara mulus tanpa ada kendala.
