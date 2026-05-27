import socket

def scan_local_database_ports():
    """Memindai port database di localhost secara otomatis"""
    active_services = []
    
    # 1. Cek Range Port MySQL/MariaDB (3306 - 3310)
    for port in range(3306, 3311):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.05)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                name = "MySQL/MariaDB" if port == 3306 else f"MySQL/MariaDB (Port {port})"
                active_services.append({"port": port, "name": name})

    # 2. Cek Port Database Lainnya
    other_ports = {5432: "PostgreSQL", 1433: "MSSQL"}
    for port, name in other_ports.items():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.05)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                active_services.append({"port": port, "name": name})
                
    return active_services

import os
import subprocess
from django.conf import settings

def execute_database_setup(host, port, user, password, db_name):
    """Fungsi helper untuk membuat database, verifikasi ulang, dan menjalankan migrasi"""
    try:
        # 1. Tes Koneksi Server & Buat Database jika belum ada
        try:
            conn = pymysql.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                connect_timeout=5
            )
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET latin1 COLLATE latin1_swedish_ci")
            conn.close()
        except Exception as e:
            return False, f"Tahap 1 Gagal (Koneksi/Pembuatan DB): {str(e)}"

        # 2. Verifikasi Ulang Koneksi ke Database yang sudah dipastikan ada
        try:
            conn = pymysql.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=db_name,
                connect_timeout=5
            )
            conn.close()
        except Exception as e:
            return False, f"Tahap 2 Gagal (Verifikasi Database `{db_name}`): {str(e)}"

        # 3. Jalankan Migrasi Django
        python_exe = os.path.join(settings.BASE_DIR, 'venv', 'Scripts', 'python.exe')
        if not os.path.exists(python_exe):
            python_exe = 'python'
            
        # Siapkan Environment Variables untuk Subprocess
        new_env = os.environ.copy()
        new_env['DB_HOST'] = str(host or '127.0.0.1')
        new_env['DB_PORT'] = str(port or '3306')
        new_env['DB_USER'] = str(user or 'root')
        new_env['DB_PASSWORD'] = str(password or '')
        new_env['DB_NAME'] = str(db_name or 'orthanc_sync')
        new_env['PYTHONPATH'] = str(settings.BASE_DIR)
        
        # Kita panggil migrate secara berurutan
        commands = [
            f'"{python_exe}" manage.py makemigrations bridge',
            f'"{python_exe}" manage.py migrate --noinput',
            f'"{python_exe}" manage.py seed_admin'
        ]
        
        for cmd in commands:
            # Gunakan env=new_env agar subprocess mendapatkan nilai terbaru
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=new_env, cwd=settings.BASE_DIR)
            if result.returncode != 0:
                return False, f"Tahap 3 Gagal pada perintah `{cmd}`: {result.stderr or result.stdout}"
        
        return True, "Konfigurasi Berhasil: Database dibuat, diverifikasi, dan dimigrasi sepenuhnya."
        
    except Exception as e:
        return False, f"Kesalahan Sistem: {str(e)}"

import pymysql

def test_db_connection(host, port, user, password, db_name=None):
    """Menguji koneksi ke server database (hanya cek service & auth)"""
    try:
        conn = pymysql.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            connect_timeout=3
        )
        conn.close()
        return True, "Koneksi ke Server Berhasil!"
    except Exception as e:
        return False, f"Koneksi Gagal: {str(e)}"

def update_env_file(updates):
    """Memperbarui file .env dengan nilai baru"""
    env_path = os.path.join(settings.BASE_DIR, '.env')
    lines = []
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
            
    # Map updates to existing lines or append new ones
    for key, value in updates.items():
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}\n")
            
    with open(env_path, 'w') as f:
        f.writelines(lines)
    
    # Update environment variabel proses saat ini
    os.environ.update({k: str(v) for k, v in updates.items()})
    
    return True
