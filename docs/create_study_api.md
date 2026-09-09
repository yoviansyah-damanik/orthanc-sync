# API Documentation: Create DICOM Study (`/api/study/create`)

API untuk menerima data study medis beserta gambar lalu membuat instance DICOM secara langsung di Orthanc PACS (`/tools/create-dicom`) dengan proteksi auto-overwrite untuk mencegah duplikasi.

## Endpoint
- **URL**: `/api/study/create`
- **Method**: `POST`
- **Auth**: Header `X-API-Key` atau Sesi Login

## Request Headers & Auth
| Format | Contoh |
|---|---|
| Header `X-API-Key` | `X-API-Key: <api-key>` |
| Header `Authorization` | `Authorization: Bearer <api-key>` |
| Query / Body Param | `?api_key=<api-key>` |

Semua request (sukses, validasi gagal, maupun error otentikasi) otomatis tercatat pada **API Audit Log** (`/api-logs/`).

## Request Body Parameters
| Field | Tipe | Wajib | Deskripsi |
|---|---|---|---|
| `accession_number` | String(16) | Ya | Accession number unik pemeriksaan |
| `patient_id` | String | Ya | Nomor rekam medis / ID pasien |
| `patient_name` | String | Ya | Nama lengkap pasien |
| `image_b64` / `image_base64` | String | Ya | Base64 data URI (JSON) atau upload berkas gambar (Multipart) |
| `modality` | String | Sangat Disarankan | Modality DICOM (contoh: `CR`, `DX`, `CT`, `MR`, `US`). Default: `OT` |
| `sop_class_uid` | String | Opsional | SOP Class UID kustom jika ingin override pemetaan otomatis |
| `procedure_desc` | String | Tidak | Deskripsi prosedur / Study Description |
| `series_description`| String | Tidak | Deskripsi series (default: `Imported Image Series`) |
| `birth_date` | String | Tidak | Format `YYYY-MM-DD` atau `YYYYMMDD` |
| `gender` | String | Tidak | `M` / `F` / `O` (default: `O`) |
| `study_date` | String | Tidak | Format `YYYYMMDD` (default: hari ini) |
| `study_time` | String | Tidak | Format `HHMMSS` (default: waktu saat ini) |

> [!IMPORTANT]
> **Penting untuk Transfer DICOM (C-STORE ke Router / PACS seperti DCMROUTER):**
> Jika field `modality` tidak diisi secara spesifik (default: `OT`), SOP Class akan diset ke *Secondary Capture* (`1.2.840.10008.5.1.4.1.1.7`). Router/PACS tujuan mungkin menolak transfer jika tidak mendukung SOP Class tersebut, menyebabkan error:
> `Unable to determine the SOP class/instance for C-STORE with AET DCMROUTER (Orthanc Error 2014)`.
> Pastikan client selalu menyertakan `modality` yang sesuai (`CR`, `DX`, `CT`, dsb.).

### Pemetaan Otomatis SOP Class UID Berdasarkan Modality
| Modality | SOP Class UID | Deskripsi Standar |
|---|---|---|
| `CR` | `1.2.840.10008.5.1.4.1.1.1` | Computed Radiography Image Storage |
| `DX` | `1.2.840.10008.5.1.4.1.1.1.1` | Digital X-Ray Image Storage - For Presentation |
| `CT` | `1.2.840.10008.5.1.4.1.1.2` | CT Image Storage |
| `MR` | `1.2.840.10008.5.1.4.1.1.4` | MR Image Storage |
| `US` | `1.2.840.10008.5.1.4.1.1.6.1` | Ultrasound Image Storage |
| `DOC` / PDF | `1.2.840.10008.5.1.4.1.1.104.1` | Encapsulated PDF Storage |
| Lainnya / `OT` | `1.2.840.10008.5.1.4.1.1.7` | Secondary Capture Image Storage |

## Anti-Duplicate Mechanism (Auto-Overwrite)
1. Sistem memanggil Orthanc `POST /tools/find` level Study dengan `AccessionNumber`.
2. Jika study sudah ada, sistem memanggil `DELETE /studies/{id}` di Orthanc.
3. Sistem membuat study baru via Orthanc `POST /tools/create-dicom` lengkap dengan `SOPClassUID`.

## Response Format

### Sukses (200 OK)
```json
{
  "success": true,
  "message": "Study DICOM untuk Accession Number 'ACC20260909001' berhasil dibuat di Orthanc PACS.",
  "overwritten": false,
  "accession_number": "ACC20260909001",
  "patient_id": "042790",
  "patient_name": "JOHN^DOE",
  "modality": "CR",
  "sop_class_uid": "1.2.840.10008.5.1.4.1.1.1",
  "orthanc_instance_id": "ba5d5129-f656b122-f9c5ed48-7ed5db98-e82d6567",
  "orthanc_study_id": "edd764cb-099a9d0f-25e5b18a-46baed85-45320354",
  "study_instance_uid": "1.2.276.0.7230010.3.1.2.1714643763.1.1788935801.392055"
}
```

*Catatan: Jika client tidak menyertakan `modality` spesifik, response akan menyertakan field `note` berisi peringatan kelengkapan data.*

### Gagal (400 Bad Request)
```json
{
  "success": false,
  "message": "Field accession_number wajib diisi."
}
```
