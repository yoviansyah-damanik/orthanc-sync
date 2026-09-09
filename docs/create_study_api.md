# API Documentation: Create DICOM Study (`/api/study/create`)

API untuk menerima data study medis beserta gambar lalu membuat instance DICOM secara langsung di Orthanc PACS (`/tools/create-dicom`) dengan proteksi auto-overwrite untuk mencegah duplikasi.

## Endpoint
- **URL**: `/api/study/create`
- **Method**: `POST`
- **Auth**: Header `X-API-Key` atau Sesi Login

## Request Headers
| Header | Value |
|---|---|
| `X-API-Key` | `<api-key-anda>` |
| `Content-Type` | `application/json` atau `multipart/form-data` |

## Request Body Parameters
| Field | Tipe | Wajib | Deskripsi |
|---|---|---|---|
| `accession_number` | String(16) | Ya | Accession number unik pemeriksaan |
| `patient_id` | String | Ya | Nomor rekam medis / ID pasien |
| `patient_name` | String | Ya | Nama lengkap pasien |
| `image_b64` / `file` | String / File | Ya | Base64 data URI (JSON) atau berkas gambar (Multipart) |
| `modality` | String | Tidak | Modality DICOM (default: `OT`) |
| `procedure_desc` | String | Tidak | Deskripsi prosedur / Study Description |
| `series_description`| String | Tidak | Deskripsi series (default: `Imported Image Series`) |
| `birth_date` | String | Tidak | Format `YYYY-MM-DD` atau `YYYYMMDD` |
| `gender` | String | Tidak | `M` / `F` / `O` (default: `O`) |
| `study_date` | String | Tidak | Format `YYYYMMDD` (default: hari ini) |
| `study_time` | String | Tidak | Format `HHMMSS` (default: waktu saat ini) |
| `study_instance_uid`| String | Tidak | UID Study kustom jika ditentukan |

## Anti-Duplicate Mechanism (Auto-Overwrite)
1. Sistem memanggil Orthanc `POST /tools/find` level Study dengan `AccessionNumber`.
2. Jika study sudah ada, sistem memanggil `DELETE /studies/{id}` di Orthanc.
3. Sistem membuat study baru via Orthanc `POST /tools/create-dicom`.

## Response Format

### Sukses (200 OK)
```json
{
  "success": true,
  "message": "Study DICOM untuk Accession Number 'ACC20260909001' berhasil dibuat di Orthanc PACS (study lama ditimpa).",
  "overwritten": true,
  "accession_number": "ACC20260909001",
  "patient_id": "042790",
  "patient_name": "JOHN^DOE",
  "orthanc_instance_id": "98e404be-ca71a629-9e8020d2-b062bbda-ea4f58bc",
  "orthanc_study_id": "384eb182-fe091395-927fe199-528574fc-be7b11d9",
  "study_instance_uid": "2.16.840.1.113669.632.20.1211.10000353112"
}
```

### Gagal (400 Bad Request)
```json
{
  "success": false,
  "message": "Field accession_number wajib diisi."
}
```
