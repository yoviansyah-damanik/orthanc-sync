# DICOM Network Discovery (DICOM Scanner)

Fitur **DICOM Scanner** memungkinkan administrator untuk memindai jaringan lokal (subnet /24) secara otomatis dan mendeteksi port DICOM yang terbuka serta melakukan verifikasi kecocokan protokol **DICOM C-ECHO (Ping)** untuk mendaftarkannya langsung ke database sistem.

## Fitur Utama
1. **Auto-Subnet Detection**: Otomatis mendeteksi IP lokal server dan memberikan rekomendasi subnet untuk dipindai (misal: `192.168.1`).
2. **Parallel Port Probing**: Melakukan scanning secara paralel menggunakan `ThreadPoolExecutor` di Python, sehingga dapat memindai seluruh subnet (/24) untuk beberapa port sekaligus dalam waktu 2-10 detik saja.
3. **C-ECHO Verification**: Memverifikasi port TCP terbuka menggunakan standar asosiasi DICOM C-ECHO via library `pynetdicom`.
4. **Interactive Registration**: Membuka modal pendaftaran interaktif untuk menyesuaikan nama perangkat dan AE Title sebelum disimpan ke sistem.
5. **Real-time Status Check**: Menguji konektivitas perangkat terdaftar kapan saja dengan tombol verifikasi C-ECHO instan.

## Detail Komponen & File

### 1. Database Model (`bridge/models.py`)
Model `DicomDevice` digunakan untuk menyimpan daftar perangkat DICOM terdaftar:
- `id` (UUID, Primary Key)
- `name` (Friendly Name)
- `host` (IP Address)
- `port` (DICOM Port)
- `ae_title` (Called AE Title)
- `status` (`online` / `offline` / `unverified`)
- `last_checked` (Timestamp pengecekan terakhir)

### 2. URL Routes (`config/urls.py`)
Mendaftarkan routing pemindaian berikut:
- `/dicom-scanner/` -> Halaman scanner utama
- `/dicom-scanner/scan` -> AJAX API pemindaian subnet
- `/dicom-scanner/verify` -> AJAX API pengiriman C-ECHO
- `/dicom-scanner/register` -> AJAX API pendaftaran/penyimpanan perangkat
- `/dicom-scanner/delete` -> AJAX API penghapusan perangkat

### 3. Backend Views & Logic (`bridge/views.py`)
Mengatur logika inti scanning dan konektivitas DICOM:
- Menggunakan `concurrent.futures.ThreadPoolExecutor` untuk memparalelkan pengecekan koneksi TCP socket.
- Mengintegrasikan class `AE` dan SOP `Verification` dari `pynetdicom` untuk membangun asosiasi DICOM dan mengirimkan C-ECHO.
- Menguji status respon perangkat secara real-time dan mengembalikan data terstruktur dalam format JSON.

### 4. Tampilan Antarmuka (`bridge/templates/dicom_scanner.html`)
Desain dashboard premium dengan:
- Animasi radar menyapu warna biru menggunakan CSS custom conic-gradient dan efek denyut pulsa berulang.
- Tabel dinamis hasil pemindaian langsung yang otomatis menyajikan tombol "Daftarkan".
- Modal overlay pendaftaran interaktif beranimasi halus.
- Toast feedback instan yang menginformasikan status verifikasi dan pendaftaran.

## Verifikasi
Pengecekan integritas sistem dijalankan dengan perintah:
```bash
python manage.py check
```
Hasil pemeriksaan melaporkan integrasi sistem berjalan dengan bersih tanpa kesalahan.
