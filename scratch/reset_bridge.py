import os
import sys
import django
from django.db import connection

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS bridge_worklistlog")
    cursor.execute("DROP TABLE IF EXISTS bridge_worklist")
    cursor.execute("DROP TABLE IF EXISTS bridge_apikey")
    cursor.execute("DROP TABLE IF EXISTS bridge_systemconfig")
    cursor.execute("DELETE FROM django_migrations WHERE app = 'bridge'")
print("Bridge tables dropped and migration history cleared.")
