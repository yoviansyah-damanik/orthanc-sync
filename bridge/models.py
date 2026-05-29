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
        except cls.DoesNotExist:
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
