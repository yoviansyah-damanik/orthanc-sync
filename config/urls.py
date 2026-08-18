from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from bridge.views import api_docs_page_view, api_logs_page_view, api_management_view, check_db_health, configuration_view, create_worklist_api, dashboard_view, database_setup_page, fix_folder_permissions, health_check_api, login_view, logout_view, profile_view, run_database_setup, test_db_api, test_orthanc_connection, worklist_detail_api, worklist_page_view, worklist_history_view, check_orthanc_study_api, check_worklist_file_api, user_guide_page_view, about_page_view, monitoring_view, monitoring_chart_api, dicom_scanner_view, dicom_scan_api, dicom_verify_api, dicom_register_api, dicom_delete_api, dicom_router_view, scheduled_backup_view, all_studies_view, orthanc_studies_api, orthanc_study_detail_api, dicom_transfer_api

from bridge.views import dicom_modify_api, routing_rules_api, sync_schedules_api, routing_logs_api, sync_logs_api
from bridge.views import upload_logo_view, reset_logo_view, upload_favicon_view, reset_favicon_view
from bridge.views import sync_modalities_to_orthanc, orthanc_modalities_api, sync_single_device_to_orthanc, sync_modality_to_local
from bridge.views import orthanc_info_view, orthanc_info_api
from bridge.views import run_schedule_now

from bridge.views import doc_modality_page_view, doc_modality_upload_api, doc_transfer_api, doc_delete_api

urlpatterns = [
    path('.well-known/appspecific/com.chrome.devtools.json', lambda r: JsonResponse({})),
    path('admin/', admin.site.urls),
    path('', dashboard_view, name='dashboard'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile_page'),
    path('worklist/', worklist_page_view, name='worklist_page'),
    path('modality-doc/', doc_modality_page_view, name='doc_modality_page'),
    path('api/modality-doc/upload', doc_modality_upload_api, name='doc_modality_upload_api'),
    path('api/doc/upload', doc_modality_upload_api, name='api_doc_upload'),
    path('api/doc/transfer', doc_transfer_api, name='doc_transfer_api'),
    path('api/doc/<str:accession_number>', doc_delete_api, name='doc_delete_api'),
    path('monitoring/', monitoring_view, name='monitoring_page'),
    path('api-logs/', api_logs_page_view, name='api_logs_page'),
    path('api-docs/', api_docs_page_view, name='api_docs_page'),
    path('api-management/', api_management_view, name='api_management'),
    path('configuration/', configuration_view, name='configuration_page'),
    path('user-guide/', user_guide_page_view, name='user_guide_page'),
    path('about/', about_page_view, name='about_page'),
    path('dicom-scanner/', dicom_scanner_view, name='dicom_scanner_page'),
    path('dicom-scanner/scan', dicom_scan_api, name='dicom_scan_api'),
    path('dicom-scanner/verify', dicom_verify_api, name='dicom_verify_api'),
    path('dicom-scanner/register', dicom_register_api, name='dicom_register_api'),
    path('dicom-scanner/delete', dicom_delete_api, name='dicom_delete_api'),
    path('dicom-router/', dicom_router_view, name='dicom_router_page'),
    path('scheduled-backup/', scheduled_backup_view, name='scheduled_backup_page'),
    path('all-studies/', all_studies_view, name='all_studies_page'),
    path('api/orthanc-studies/', orthanc_studies_api, name='orthanc_studies_api'),
    path('api/orthanc-studies/<str:study_id>/', orthanc_study_detail_api, name='orthanc_study_detail_api'),
    path('api/dicom-transfer/', dicom_transfer_api, name='dicom_transfer_api'),
    path('api/dicom-modify/<str:study_id>/', dicom_modify_api, name='dicom_modify_api'),
    path('api/routing-rules/', routing_rules_api, name='routing_rules_api'),
    path('api/sync-schedules/', sync_schedules_api, name='sync_schedules_api'),
    path('api/routing-logs/', routing_logs_api, name='routing_logs_api'),
    path('api/sync-logs/', sync_logs_api, name='sync_logs_api'),
    path('configuration/test-orthanc', test_orthanc_connection, name='test_orthanc'),
    path('configuration/fix-permissions', fix_folder_permissions, name='fix_permissions'),
    path('setup-database/', database_setup_page, name='database_setup_page'),
    path('api/status', health_check_api, name='api_status'),
    path('api/worklist', create_worklist_api, name='api_worklist'),
    path('api/worklist/<str:accession_number>', worklist_detail_api, name='worklist_detail'),
    path('api/worklist/<str:accession_number>/history', worklist_history_view, name='worklist_history'),
    path('api/check-study/<str:accession_number>', check_orthanc_study_api, name='check_study_api'),
    path('api/check-wl/<str:accession_number>', check_worklist_file_api, name='check_wl_api'),
    path('api/setup-database', run_database_setup, name='run_database_setup'),
    path('api/check-db', check_db_health, name='check_db_health'),
    path('api/test-db', test_db_api, name='test_db_api'),
    path('api/monitoring-chart/', monitoring_chart_api, name='monitoring_chart_api'),
    path('orthanc-info/', orthanc_info_view, name='orthanc_info_page'),
    path('api/run-schedule/<str:schedule_id>/', run_schedule_now, name='run_schedule_now'),
    path('api/orthanc-info/', orthanc_info_api, name='orthanc_info_api'),
    path('configuration/upload-logo', upload_logo_view, name='upload_logo'),
    path('configuration/reset-logo', reset_logo_view, name='reset_logo'),
    path('configuration/upload-favicon', upload_favicon_view, name='upload_favicon'),
    path('configuration/reset-favicon', reset_favicon_view, name='reset_favicon'),
    path('api/sync-modalities/', sync_modalities_to_orthanc, name='sync_modalities'),
    path('api/sync-modalities/<str:device_id>/', sync_single_device_to_orthanc, name='sync_single_modality'),
    path('api/orthanc-modalities/', orthanc_modalities_api, name='orthanc_modalities_api'),
    path('api/sync-modality-to-local/', sync_modality_to_local, name='sync_modality_to_local'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'bridge.views.error_404_view'
handler500 = 'bridge.views.error_500_view'
