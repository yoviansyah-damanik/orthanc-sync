# Orthanc Bridge (Orthanc Sync)

Sistem integrasi berbasis web premium untuk server PACS Orthanc. Menyediakan sinkronisasi worklist DICOM, pemindaian jaringan, PACS browser, dan perutean node.

## Fitur

- **Dashboard**: Tinjauan sistem, konektivitas server, dan statistik sinkronisasi.
- **Worklist Manager**: Kelola dan kirim Modality Worklist DICOM ke modalitas.
- **PACS Browser**: Cari, jelajah, dan lihat studi DICOM via OHIF Viewer tersemat, serta transfer node (C-STORE).
- **DICOM Router**: Registrasi dan uji koneksi (C-ECHO) remote PACS / modalitas.
- **DICOM Network Scanner**: Pemindaian subnet paralel untuk mendaftarkan perangkat DICOM otomatis.
- **Logs**: Audit real-time data API worklist masuk & keluar.

---

## Prasyarat

| Komponen | Versi Minimum | Keterangan |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) |
| MySQL / MariaDB | 8.0+ / 10.6+ | Database utama |
| Orthanc PACS | 1.11+ | [orthanc-server.com](https://www.orthanc-server.com) |

---

## Instalasi

### 1. Clone Repository & Setup Venv
```bash
git clone https://github.com/yoviansyah-damanik/orthanc-sync.git
cd orthanc-sync

# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependensi
```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Environment
Salin berkas template lingkungan:
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```
Edit file `.env` untuk menyesuaikan database (`DB_NAME`, `DB_USER`, `DB_PASSWORD`), `SECRET_KEY`, dan nama RS (`HOSPITAL_NAME`).

### 4. Setup Database & Akun
```bash
# Buat database kosong di MySQL:
# CREATE DATABASE orthanc_sync CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# Jalankan migrasi
python manage.py migrate

# Buat superuser
python manage.py createsuperuser
```

### 5. Generate Watermark Hash (Wajib)
Jalankan perintah ini sekali setelah instalasi agar sistem tidak terkunci:
```bash
python manage.py generate_watermark_hash
```

### 6. Jalankan Aplikasi
```bash
python manage.py runserver 0.0.0.0:9123
```
Akses via browser di: **http://localhost:9123**

---

## Verifikasi & Troubleshooting

Jalankan cek integritas:
```bash
python manage.py check
```

| Masalah | Solusi |
|---|---|
| `Unknown database` | Pastikan database sudah dibuat di MySQL |
| `No module named ...` | Jalankan `pip install -r requirements.txt` |
| Halaman **"Lisensi Tidak Valid"** | Jalankan `python manage.py generate_watermark_hash` |
| Orthanc **Disconnected** | Periksa konfigurasi URL & kredensial Orthanc di Pengaturan |

---

## Struktur Proyek

- `bridge/`: Logika bisnis, views, models, dan API Django.
- `config/`: Konfigurasi proyek Django.
- `docs/`: Dokumentasi teknis lengkap.
- `static/` & `templates/`: Aset frontend dan tampilan antarmuka.

---

## Dokumentasi Lengkap

Detail fitur di direktori [`docs/`](docs/):
- [PACS Browser & OHIF Viewer](docs/all_studies.md)
- [DICOM Router & Nodes](docs/dicom_router.md)
- [DICOM Network Scanner](docs/dicom_scanner.md)
- [Bridge Web Services API](docs/bridge-api.md)

---

## Pengembang

<a href="https://instagram.com/yoviansyah_damanik" target="_blank">
  <img src="https://img.shields.io/badge/Instagram-@yoviansyah__damanik-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram Profile"/>
</a>
<a href="https://wa.me/6281222778197" target="_blank" rel="noopener">
  <img src="https://img.shields.io/badge/WhatsApp-0812--2277--8197-25D366?style=for-the-badge&logo=whatsapp&logoColor=white" alt="WhatsApp Contact"/>
</a>

### **Yoviansyah Rizki Pratama, S.Kom**
- **Peran**: Full-Stack Developer
- **WhatsApp**: `+62 812-2277-8197`
- **Instagram**: [`@yoviansyah_damanik`](https://instagram.com/yoviansyah_damanik)
