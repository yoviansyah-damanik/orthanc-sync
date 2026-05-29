"""
Management command: generate_watermark_hash
Mengambil blok watermark dari base.html, menghitung SHA-256, dan menyimpannya ke .env
"""
import hashlib
import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

TEMPLATE_PATH = os.path.join(settings.BASE_DIR, 'bridge', 'templates', 'base.html')
ENV_PATH = os.path.join(settings.BASE_DIR, '.env')
MARKER_START = '<!-- WATERMARK_START -->'
MARKER_END = '<!-- WATERMARK_END -->'
ENV_KEY = 'WATERMARK_HASH'


def extract_watermark_block(content: str) -> str:
    """Mengambil teks di antara marker WATERMARK_START dan WATERMARK_END."""
    start = content.find(MARKER_START)
    end = content.find(MARKER_END)
    if start == -1 or end == -1:
        return ''
    return content[start:end + len(MARKER_END)]


def compute_hash(block: str) -> str:
    """Menghitung SHA-256 dari blok watermark (normalized whitespace)."""
    normalized = ' '.join(block.split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def update_env(key: str, value: str) -> None:
    """Memperbarui atau menambahkan key ke file .env."""
    lines = []
    found = False

    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith(f'{key}='):
            new_lines.append(f'{key}={value}\n')
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f'{key}={value}\n')

    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)


class Command(BaseCommand):
    help = 'Generate & simpan hash watermark dari base.html ke file .env'

    def handle(self, *args, **kwargs):
        if not os.path.exists(TEMPLATE_PATH):
            raise CommandError(f'Template tidak ditemukan: {TEMPLATE_PATH}')

        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        block = extract_watermark_block(content)
        if not block:
            raise CommandError(
                'Blok watermark tidak ditemukan. '
                'Pastikan marker <!-- WATERMARK_START --> dan <!-- WATERMARK_END --> ada di base.html.'
            )

        hash_value = compute_hash(block)
        update_env(ENV_KEY, hash_value)

        # Set ke environment aktif agar middleware langsung pakai
        os.environ[ENV_KEY] = hash_value

        self.stdout.write(self.style.SUCCESS(f'[OK] Watermark hash berhasil disimpan ke .env'))
        self.stdout.write(self.style.SUCCESS(f'     {ENV_KEY}={hash_value}'))
