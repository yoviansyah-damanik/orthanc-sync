import uuid
import secrets
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    def __str__(self):
        return self.username

class APIKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Nama aplikasi/sistem pemanggil")
    key = models.CharField(max_length=64, unique=True, blank=True)
    webhook_url = models.URLField(max_length=500, null=True, blank=True, help_text="URL callback default untuk sistem ini")
    webhook_username = models.CharField(max_length=150, null=True, blank=True, help_text="Username untuk Basic Auth callback")
    webhook_password = models.CharField(max_length=150, null=True, blank=True, help_text="Password untuk Basic Auth callback")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

class Worklist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """Model untuk menyimpan data worklist yang aktif/tersimpan saat ini"""
    accession_number = models.CharField(max_length=50, unique=True)
    patient_id = models.CharField(max_length=50)
    patient_name = models.CharField(max_length=255)
    modality = models.CharField(max_length=50)
    birth_date = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    procedure_desc = models.CharField(max_length=255, blank=True, null=True)
    scheduled_date = models.CharField(max_length=20, blank=True, null=True)
    ae_title = models.CharField(max_length=50, blank=True, null=True)
    study_instance_uid = models.CharField(max_length=100, blank=True, null=True)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, default="Berhasil")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.accession_number} - {self.patient_name}"

    class Meta:
        ordering = ['-updated_at']

class DocDocument(models.Model):
    """Model untuk menyimpan dokumen medis (PDF/Citra) hasil enkapsulasi Modality DOC.
    Terpisah dari Worklist agar tidak ikut tercatat sebagai jadwal worklist modality nyata."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    accession_number = models.CharField(max_length=50, unique=True)
    patient_id = models.CharField(max_length=50)
    patient_name = models.CharField(max_length=255)
    birth_date = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    procedure_desc = models.CharField(max_length=255, blank=True, null=True)
    study_instance_uid = models.CharField(max_length=100, blank=True, null=True)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, default="Berhasil")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.accession_number} - {self.patient_name}"

    class Meta:
        ordering = ['-created_at']

class WorklistLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """Model untuk audit log setiap request API (Success, Error, Duplicate, dll)"""
    accession_number = models.CharField(max_length=50)
    patient_name = models.CharField(max_length=255)
    method = models.CharField(max_length=10, default="POST")
    status = models.CharField(max_length=20) # "Berhasil" / "Gagal" / "Dihapus" / "Duplikat" / "Updated"
    raw_payload = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.accession_number} - {self.status} @ {self.created_at}"

    class Meta:
        ordering = ['-created_at']

class SystemConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=50, unique=True)
    value = models.TextField()
    description = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key}: {self.value}"

    @classmethod
    def get_val(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except Exception:
            return default

class DicomDevice(models.Model):
    """Menyimpan perangkat DICOM yang ditemukan/terdaftar dalam jaringan"""
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('unverified', 'Belum Diverifikasi'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Nama deskriptif perangkat")
    ae_title = models.CharField(max_length=64, blank=True, default='', help_text="DICOM AE Title")
    host = models.GenericIPAddressField(help_text="IP Address perangkat")
    port = models.PositiveIntegerField(default=104, help_text="Port DICOM")
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unverified')
    last_checked = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.ae_title}) - {self.host}:{self.port}"

    class Meta:
        ordering = ['host', 'port']


# ─── 1. AUTO-ROUTING MODELS ───────────────────────────────────────────────

class RoutingRule(models.Model):
    """Model untuk menyimpan aturan perutean DICOM otomatis"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, help_text="Nama aturan perutean")
    modality = models.CharField(max_length=50, blank=True, default="", help_text="Filter Modality (cth: CT, MR, DX) atau kosongkan untuk semua")
    patient_id_prefix = models.CharField(max_length=50, blank=True, default="", help_text="Prefiks Patient ID atau kosongkan untuk semua")
    study_desc_contains = models.CharField(max_length=255, blank=True, default="", help_text="Filter deskripsi studi mengandung teks")
    target_device = models.ForeignKey(DicomDevice, on_delete=models.CASCADE, related_name="routing_rules", help_text="Node DICOM tujuan perutean")
    is_active = models.BooleanField(default=True, help_text="Aturan aktif atau tidak")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} -> {self.target_device.name}"


class RoutingLog(models.Model):
    """Model untuk mencatat riwayat perutean otomatis yang dijalankan"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(RoutingRule, on_delete=models.SET_NULL, null=True, blank=True)
    study_id = models.CharField(max_length=100)
    patient_name = models.CharField(max_length=255)
    modality = models.CharField(max_length=50)
    target_device_name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, default="Pending") # Success, Failed
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# ─── 2. SCHEDULED PACS BACKUP MODELS ───────────────────────────────────────

class SyncSchedule(models.Model):
    """Model untuk menjadwalkan pengiriman otomatis studi DICOM ke node tujuan"""
    FREQUENCY_CHOICES = [
        ('hourly', 'Setiap Jam'),
        ('daily',  'Setiap Hari'),
        ('weekly', 'Setiap Minggu (Hari Minggu)'),
    ]
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name            = models.CharField(max_length=150)
    target_device   = models.ForeignKey(DicomDevice, on_delete=models.CASCADE, related_name="sync_schedules")
    frequency       = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    run_hour        = models.PositiveSmallIntegerField(default=0, help_text='Jam pengiriman (0-23) untuk jadwal harian/mingguan')
    run_minute      = models.PositiveSmallIntegerField(default=0, help_text='Menit pengiriman (0-59)')
    modality_filter = models.CharField(max_length=100, blank=True, default='', help_text='Filter modalitas cth: CT,MR — kosongkan untuk semua')
    last_run        = models.DateTimeField(null=True, blank=True)
    next_run        = models.DateTimeField(null=True, blank=True)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()}) -> {self.target_device.name}"


class SyncLog(models.Model):
    """Model untuk riwayat sinkronisasi/pencadangan PACS"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.ForeignKey(SyncSchedule, on_delete=models.SET_NULL, null=True, blank=True)
    total_studies = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20) # Success, Failed, Partial
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class TransferLog(models.Model):
    """Model untuk mencatat riwayat transfer DICOM manual"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    study_id = models.CharField(max_length=100) # ID study di Orthanc
    patient_name = models.CharField(max_length=255) # Nama pasien
    patient_id = models.CharField(max_length=100, blank=True, default="") # ID pasien
    accession_number = models.CharField(max_length=50, blank=True, default="") # Nomor aksesi
    modality = models.CharField(max_length=50, blank=True, default="") # Modalitas
    target_device = models.ForeignKey(DicomDevice, on_delete=models.SET_NULL, null=True, blank=True) # Perangkat DICOM tujuan
    target_device_name = models.CharField(max_length=150) # Nama perangkat tujuan (backup jika terhapus)
    status = models.CharField(max_length=20, default="Success") # Status transfer (Success / Failed)
    error_message = models.TextField(blank=True, null=True) # Pesan kesalahan jika gagal
    created_at = models.DateTimeField(auto_now_add=True) # Waktu pencatatan transfer

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.patient_name} -> {self.target_device_name} ({self.status})"


