from django.contrib import admin
from django.urls import path
from bridge.views import api_docs_page_view, api_logs_page_view, api_management_view, check_db_health, configuration_view, create_worklist_api, dashboard_view, database_setup_page, fix_folder_permissions, health_check_api, login_view, logout_view, profile_view, run_database_setup, test_db_api, test_orthanc_connection, worklist_detail_api, worklist_page_view, worklist_history_view, check_orthanc_study_api, check_worklist_file_api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_view, name='dashboard'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile_page'),
    path('worklist/', worklist_page_view, name='worklist_page'),
    path('api-logs/', api_logs_page_view, name='api_logs_page'),
    path('api-docs/', api_docs_page_view, name='api_docs_page'),
    path('api-management/', api_management_view, name='api_management'),
    path('configuration/', configuration_view, name='configuration_page'),
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
]

handler404 = 'bridge.views.error_404_view'
handler500 = 'bridge.views.error_500_view'
