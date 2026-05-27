import os
import requests
from django.utils import timezone
from django.db import OperationalError
from .models import SystemConfig

def orthanc_status(request):
    """
    Context processor untuk mengecek status koneksi Orthanc di setiap halaman.
    Menggunakan cache sederhana agar tidak memperlambat loading.
    """
    context = {
        'app_name': os.getenv('APP_NAME', 'Orthanc Bridge'),
        'hospital_name': os.getenv('HOSPITAL_NAME', 'Rumah Sakit'),
        'current_year': timezone.now().year,
    }

    if not request.user.is_authenticated:
        return context

    try:
        url = SystemConfig.get_val('ORTHANC_URL', 'http://localhost:8042')
        user = SystemConfig.get_val('ORTHANC_USER', 'orthanc')
        password = SystemConfig.get_val('ORTHANC_PASS', 'orthanc')
        
        status = "offline"
        # Timeout sangat singkat agar tidak mengganggu UX
        response = requests.get(
            f"{url.rstrip('/')}/system",
            auth=(user, password),
            timeout=0.5 
        )
        if response.status_code == 200:
            status = "online"
        context['orthanc_status'] = status
    except:
        # Jika DB belum ada (SystemConfig fails) atau Orthanc offline
        context['orthanc_status'] = "offline"
        
    return context
def sidebar_data(request):
    """
    Menyediakan data menu sidebar yang terpusat agar konsisten antara
    tampilan desktop dan mobile.
    """
    if not request.user.is_authenticated:
        return {}

    menu_structure = [
        {
            'group': 'Overview',
            'items': [
                {
                    'name': 'Ringkasan',
                    'url': 'dashboard',
                    'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>'
                },
            ]
        },
        {
            'group': 'Manajemen Data',
            'items': [
                {
                    'name': 'Worklist',
                    'url': 'worklist_page',
                    'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path>'
                },
                {
                    'name': 'API Log',
                    'url': 'api_logs_page',
                    'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>'
                },
            ]
        },
        {
            'group': 'Sistem',
            'items': [
                {
                    'name': 'Petunjuk API',
                    'url': 'api_docs_page',
                    'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5S19.832 5.477 21 6.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>'
                },
                {
                    'name': 'Manajemen API',
                    'url': 'api_management',
                    'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>'
                },
                {
                    'name': 'Konfigurasi',
                    'url': 'configuration_page',
                    'icon': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>'
                },
            ]
        }
    ]

    return {'sidebar_menu': menu_structure}
