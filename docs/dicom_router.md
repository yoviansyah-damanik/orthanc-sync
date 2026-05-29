# DICOM Router & Node Management

Fitur **DICOM Router** menyediakan panel terpusat yang tangguh dan estetis untuk mengelola target peer/node DICOM (PACS, Modality, atau DICOM Server lainnya). Halaman ini menampilkan seluruh perangkat yang terdaftar (baik hasil dari pemindaian otomatis via **DICOM Scanner** maupun yang diinput manual).

## Fitur Utama

1. **Dual-Pane UI**:
   * **Form Kiri**: Form pendaftaran & pembaruan node manual (interaktif, adaptif, mendukung auto-fill mode pengeditan).
   * **Grid Kanan**: Menampilkan koleksi kartu node DICOM terdaftar dengan detail host, port, Called AE Title, dan status waktu periksa terakhir.
2. **Dynamic CRUD Forms**:
   * Pengguna dapat mendaftarkan perangkat baru secara manual tanpa perlu melakukan scan jaringan terlebih dahulu.
   * Tombol **Edit** (ikon pensil) secara otomatis mengisi data kartu ke form kiri untuk diubah dan disimpan dengan aman.
3. **Real-time C-ECHO Verification**:
   * Tombol **Test Ping** mengirimkan perintah DICOM C-ECHO (Ping) menggunakan library `pynetdicom` secara asinkron (AJAX).
   * Menampilkan respon visual langsung (Online dengan indikator hijau berdenyut, Offline dengan indikator merah, atau Unverified dengan indikator jingga) beserta waktu verifikasi terakhir.
4. **Fluid Transitions**:
   * Penghapusan kartu perangkat terdaftar dirancang dengan transisi memudar yang halus menggunakan kelas Tailwind CSS.

## Detail Implementasi Komponen

### 1. Backend Views (`bridge/views.py`)
* Menambahkan view `dicom_router_view(request)` yang memuat seluruh data dari model `DicomDevice` dan merender template `dicom_router.html`.
* Memanfaatkan kembali API endpoint CRUD yang sudah dibuat sebelumnya agar kode tetap bersih dan modular:
  * `/dicom-scanner/register` -> Dipanggil untuk menyimpan pendaftaran baru maupun perubahan edit data perangkat.
  * `/dicom-scanner/verify` -> Menguji konektivitas standard DICOM C-ECHO.
  * `/dicom-scanner/delete` -> Menghapus perangkat dari database.

### 2. URL Patterns (`config/urls.py`)
* Menghubungkan path `/dicom-router/` ke view `dicom_router_view` dengan nama path `dicom_router_page`.

### 3. Sidebar Menu (`bridge/context_processors.py`)
* Menyematkan menu **DICOM Router** di dalam kelompok menu "Manajemen Data" dengan SVG icon cross-arrows yang melambangkan fungsi routing/node peer.

---

## Verifikasi Teknis

Aplikasi telah divalidasi dengan perintah pemeriksaan Django:
```bash
python manage.py check
```
Pemeriksaan melaporkan integrasi berjalan bersih 100% tanpa adanya kesalahan tautan maupun dependensi library.
