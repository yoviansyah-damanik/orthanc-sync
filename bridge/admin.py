from django.contrib import admin
from .models import User, APIKey, Worklist, DocDocument, WorklistLog, SystemConfig, DicomDevice, RoutingRule, RoutingLog, SyncSchedule, SyncLog

admin.site.register(User)

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'is_active', 'created_at', 'last_used')
    search_fields = ('name',)

@admin.register(Worklist)
class WorklistAdmin(admin.ModelAdmin):
    list_display = ('accession_number', 'patient_id', 'patient_name', 'modality', 'status', 'is_active', 'created_at')
    search_fields = ('accession_number', 'patient_id', 'patient_name')
    list_filter = ('modality', 'status', 'is_active')

@admin.register(DocDocument)
class DocDocumentAdmin(admin.ModelAdmin):
    list_display = ('accession_number', 'patient_id', 'patient_name', 'status', 'created_at')
    search_fields = ('accession_number', 'patient_id', 'patient_name')
    list_filter = ('status',)

@admin.register(WorklistLog)
class WorklistLogAdmin(admin.ModelAdmin):
    list_display = ('accession_number', 'patient_name', 'status', 'method', 'created_at')
    list_filter = ('status', 'method')

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'updated_at')
    search_fields = ('key',)

@admin.register(DicomDevice)
class DicomDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'ae_title', 'host', 'port', 'status', 'last_checked')
    list_filter = ('status',)
    search_fields = ('name', 'ae_title', 'host')

@admin.register(RoutingRule)
class RoutingRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'modality', 'patient_id_prefix', 'target_device', 'is_active', 'created_at')
    list_filter = ('is_active', 'modality')
    search_fields = ('name', 'patient_id_prefix')

@admin.register(RoutingLog)
class RoutingLogAdmin(admin.ModelAdmin):
    list_display = ('rule', 'patient_name', 'modality', 'target_device_name', 'status', 'created_at')
    list_filter = ('status', 'modality')
    search_fields = ('patient_name', 'study_id')

@admin.register(SyncSchedule)
class SyncScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'target_device', 'frequency', 'last_run', 'next_run', 'is_active')
    list_filter = ('frequency', 'is_active')
    search_fields = ('name',)

@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'total_studies', 'status', 'created_at')
    list_filter = ('status',)

