# Orthanc Bridge (Orthanc Sync)

Orthanc Bridge is a premium web-based integration layer for the Orthanc PACS server, providing advanced DICOM worklist synchronization, network scanning, PACS data browsing, and node routing capabilities.

## Features

- **Dashboard**: High-level system overview, server connectivity status, and sync stats.
- **Worklist Manager**: Add, manage, and push DICOM Modality Worklists to target modalities.
- **PACS Browser (All Studies)**: Fast DICOM query/retrieve interface to search, browse, and view DICOM studies.
  - **Embedded OHIF Viewer**: Open and view DICOM studies inside a modern, embedded OHIF web viewer with proper layout adjustments.
  - **DICOM Node Transfer (C-STORE)**: Push study files to registered remote DICOM nodes dynamically.
- **DICOM Router**: Register, test connection (C-ECHO), and manage remote PACS / DICOM modalities.
- **DICOM Network Scanner**: Parallel multi-port subnet scanner to discover DICOM devices on local networks, pull Called AE Titles, and auto-register them.
- **Monitoring & API Logs**: Real-time auditing of incoming and outgoing worklist API payloads.

---

## Prasyarat

| Komponen | Versi Minimum | Keterangan |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) |
| MySQL / MariaDB | 8.0+ / 10.6+ | Database utama aplikasi |
| Orthanc PACS | 1.11+ | [orthanc-server.com](https://www.orthanc-server.com) |
| pip | 23+ | Sudah termasuk dalam Python |

> **Catatan:** Orthanc harus sudah berjalan dan dapat diakses sebelum aplikasi dikonfigurasi.

---

## Instalasi

### 1. Clone Repository

```bash
git clone https://github.com/yoviansyah-damanik/orthanc-sync.git
cd orthanc-sync
```

### 2. Buat Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependensi

```bash
pip install -r requirements.txt
```

Paket utama yang akan terinstal:

| Paket | Fungsi |
|---|---|
| `django` | Web framework utama |
| `pymysql` | Koneksi MySQL / MariaDB |
| `pynetdicom` | Komunikasi DICOM (C-ECHO, C-STORE, C-FIND) |
| `pydicom` | Parsing file DICOM |
| `fastapi` + `uvicorn` | API server worklist (berjalan paralel) |
| `python-dotenv` | Manajemen environment variables |
| `requests` | HTTP client ke Orthanc REST API |

### 4. Konfigurasi Environment

Buat file `.env` di root project:

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit `.env` sesuai dengan konfigurasi lokal:

```env
DEBUG=True
SECRET_KEY=ganti-dengan-secret-key-yang-kuat

# Database MySQL
DB_NAME=orthanc_sync
DB_USER=root
DB_PASSWORD=password_anda
DB_HOST=127.0.0.1
DB_PORT=3306

# Identitas Aplikasi
APP_NAME=Orthanc Bridge
HOSPITAL_NAME=Nama Rumah Sakit Anda
```

> **Catatan:** `SECRET_KEY` dapat dibuat dengan perintah:
> ```bash
> python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

### 5. Buat Database

Buat database kosong di MySQL terlebih dahulu:

```sql
CREATE DATABASE orthanc_sync CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 6. Jalankan Migrasi Database

```bash
python manage.py migrate
```

### 7. Buat Akun Administrator

```bash
python manage.py createsuperuser
```

Ikuti prompt untuk mengisi username, email (opsional), dan password.

### 8. Generate Watermark Hash (Wajib)

Langkah ini **wajib** dilakukan satu kali setelah instalasi. Tanpa ini, middleware proteksi akan memblokir semua akses.

```bash
python manage.py generate_watermark_hash
```

Output yang diharapkan:
```
[OK] Watermark hash berhasil disimpan ke .env
     WATERMARK_HASH=<sha256-hash>
```

### 9. Kumpulkan Static Files (Produksi)

```bash
python manage.py collectstatic --noinput
```

> Langkah ini hanya diperlukan untuk deployment produksi. Development tidak membutuhkan ini.

### 10. Jalankan Aplikasi

```bash
# Development (akses dari semua IP, port 9123)
python manage.py runserver 0.0.0.0:9123

# Atau port default Django
python manage.py runserver
```

Buka browser dan akses: **http://localhost:9123**

---

## Konfigurasi Orthanc

Setelah login, buka menu **Pengaturan** dan isi:

| Parameter | Contoh Nilai | Keterangan |
|---|---|---|
| Orthanc URL | `http://localhost:8042` | URL REST API Orthanc |
| Orthanc Username | `orthanc` | Default user Orthanc |
| Orthanc Password | `orthanc` | Default password Orthanc |

---

## Verifikasi Sistem

Jalankan pengecekan integritas Django:

```bash
python manage.py check
```

Output yang diharapkan: `System check identified no issues (0 silenced).`

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| `OperationalError: (1049, "Unknown database")` | Pastikan database sudah dibuat di MySQL |
| `ModuleNotFoundError: No module named 'pynetdicom'` | Jalankan `pip install -r requirements.txt` ulang |
| Halaman menampilkan **"Lisensi Tidak Valid"** | Jalankan `python manage.py generate_watermark_hash` |
| Orthanc status **Disconnected** | Periksa URL, username, dan password Orthanc di Pengaturan |
| Port 9123 sudah digunakan | Ganti port: `python manage.py runserver 0.0.0.0:9124` |

---

## Project Structure

- `bridge/`: Main Django application containing views, models, APIs, and business logic.
- `config/`: Django project settings, routing, and configurations.
- `docs/`: Technical documentation and feature walk-throughs.
- `static/`: Frontend visual assets, scripts, and styling.
- `templates/`: Django HTML templates with high-performance responsive styling.

---

## Dokumentasi Lengkap

Lihat direktori [`docs/`](docs/) untuk dokumentasi teknis setiap modul:

- [PACS Browser & OHIF Viewer](docs/all_studies.md)
- [DICOM Router & Nodes](docs/dicom_router.md)
- [DICOM Network Scanner](docs/dicom_scanner.md)
- [Bridge Web Services API](docs/bridge-api.md)

---

## Developer & Creator Profile

<a href="https://instagram.com/yoviansyah_damanik" target="_blank">
  <img src="https://img.shields.io/badge/Instagram-@yoviansyah__damanik-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram Profile"/>
</a>
<a href="tel:081222778197">
  <img src="https://img.shields.io/badge/WhatsApp-0812--2277--8197-25D366?style=for-the-badge&logo=whatsapp&logoColor=white" alt="WhatsApp Contact"/>
</a>

### **Yoviansyah Rizki Pratama, S.Kom**

- **Role**: Full-Stack Developer
- **Phone**: `+62 812-2277-8197`
- **Instagram**: [`@yoviansyah_damanik`](https://instagram.com/yoviansyah_damanik)
