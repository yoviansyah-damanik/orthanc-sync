# Orthanc-Sync Bridge API Documentation

API internal untuk pengelolaan file DICOM Worklist (.wl).

## Authentication
Gunakan header `X-API-Key` untuk semua request.

## Endpoints

### 1. Create/Update Worklist
**POST/PUT** `/api/worklist`

Membuat atau memperbarui file worklist di server.

**Payload:**
- `accession_number` (string)
- `patient_id` (string)
- `patient_name` (string)
- `modality` (string)
- `scheduled_date` (string: YYYY-MM-DD)
- `ae_title` (string)
- `bypass` (boolean) - Jika true, timpa file jika sudah ada.

### 2. Get Worklist Detail
**GET** `/api/worklist/{accession_number}`

### 3. Delete Worklist
**DELETE** `/api/worklist/{accession_number}`

### 4. Check Orthanc Study
**GET** `/api/check-study/{accession_number}`

Mengecek apakah study dengan Accession Number tertentu sudah masuk ke Orthanc dan menghitung jumlah instance yang tersedia.

**Response:**
- `success` (boolean)
- `exists` (boolean)
- `instances_count` (int)
- `study_id` (string, jika ada)
- `study_instance_uid` (string, jika ada)

### 5. Check Worklist File (.wl)
**GET** `/api/check-wl/{accession_number}`

Mengecek apakah file `.wl` (DICOM Worklist) tersedia secara fisik di folder penyimpanan dan terdaftar di database.

**Response:**
- `success` (boolean)
- `exists` (boolean) - True jika ditemukan secara fisik atau di database.
- `physically_present` (boolean) - True jika file .wl ada di disk.
- `database_record` (boolean) - True jika terdaftar di database sistem.

### 6. Health Check
**GET** `/api/status`

Mengecek status database dan izin tulis folder worklist.

