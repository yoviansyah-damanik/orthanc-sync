import json
import os
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from bridge.models import APIKey, Worklist, DocDocument, WorklistLog, SystemConfig

User = get_user_model()

class WorklistValidationTestCase(TestCase):
    def setUp(self):
        # Inisialisasi data test user dan API Key
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.api_key = APIKey.objects.create(name='TestSystem', key='testsecretkey123')
        self.client = Client()
        
        # Bersihkan data worklist, log, dan file fisik dari tes sebelumnya
        Worklist.objects.filter(accession_number__iexact='ACSN-TEST-001').delete()
        WorklistLog.objects.filter(accession_number__iexact='ACSN-TEST-001').delete()

        dirs_to_check = [
            SystemConfig.get_val('WORKLIST_DIR', 'C:/Orthanc/Worklists'),
            'C:/Orthanc/Worklists',
            'C:\\Orthanc\\Worklists',
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'worklists')
        ]
        for wl_d in set(dirs_to_check):
            if os.path.exists(wl_d):
                tf = os.path.join(wl_d, 'ACSN-TEST-001.wl')
                if os.path.exists(tf):
                    try:
                        os.remove(tf)
                    except Exception:
                        pass

    def tearDown(self):
        Worklist.objects.filter(accession_number__iexact='ACSN-TEST-001').delete()
        dirs_to_check = [
            SystemConfig.get_val('WORKLIST_DIR', 'C:/Orthanc/Worklists'),
            'C:/Orthanc/Worklists',
            'C:\\Orthanc\\Worklists'
        ]
        for wl_d in set(dirs_to_check):
            if os.path.exists(wl_d):
                tf = os.path.join(wl_d, 'ACSN-TEST-001.wl')
                if os.path.exists(tf):
                    try:
                        os.remove(tf)
                    except Exception:
                        pass

    def test_duplicate_accession_number_validation(self):
        # Pengujian validasi duplikasi Accession Number pada create_worklist_api
        payload = {
            "accession_number": "ACSN-TEST-001",
            "patient_id": "RM-001",
            "patient_name": "Doe^John",
            "modality": "CT",
            "scheduled_date": "2026-07-29"
        }

        # Request 1: Harus berhasil
        res1 = self.client.post(
            reverse('api_worklist'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_API_KEY='testsecretkey123'
        )
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.json().get('success'))

        # Request 2 (Duplicate ACSN tanpa bypass): Harus ditolak dengan status 409
        res2 = self.client.post(
            reverse('api_worklist'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_API_KEY='testsecretkey123'
        )
        self.assertEqual(res2.status_code, 409)
        self.assertFalse(res2.json().get('success'))
        self.assertEqual(res2.json().get('error_code'), 'DUPLICATE_ACCESSION_NUMBER')

        # Request 3 (Duplicate ACSN dengan bypass=True): Harus berhasil di-update
        payload['bypass'] = True
        res3 = self.client.post(
            reverse('api_worklist'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_API_KEY='testsecretkey123'
        )
        self.assertEqual(res3.status_code, 200)
        self.assertTrue(res3.json().get('is_update'))


class DocModalityTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='docuser', password='password123')
        self.api_key = APIKey.objects.create(name='DocSystem', key='dockey123')
        self.client = Client()
        
        DocDocument.objects.filter(accession_number='ACSN-DOC-TEST').delete()
        wl_dir = SystemConfig.get_val('WORKLIST_DIR', 'C:/Orthanc/Worklists')
        test_file = os.path.join(wl_dir, 'ACSN-DOC-TEST.wl')
        if os.path.exists(test_file):
            try:
                os.remove(test_file)
            except Exception:
                pass

    def tearDown(self):
        wl_dir = SystemConfig.get_val('WORKLIST_DIR', 'C:/Orthanc/Worklists')
        test_file = os.path.join(wl_dir, 'ACSN-DOC-TEST.wl')
        if os.path.exists(test_file):
            try:
                os.remove(test_file)
            except Exception:
                pass

    def test_doc_modality_page_access(self):
        # Pengujian akses ke halaman Modality DOC
        self.client.login(username='docuser', password='password123')
        response = self.client.get(reverse('doc_modality_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Manajemen Modality DOC')

    def test_doc_modality_upload_json_b64(self):
        # Pengujian API enkapsulasi dokumen via Base64 JSON
        import base64
        sample_pdf_bytes = b"%PDF-1.4 sample pdf content for testing encapsulation"
        b64_str = base64.b64encode(sample_pdf_bytes).decode('utf-8')

        payload = {
            "accession_number": "ACSN-DOC-TEST",
            "patient_id": "RM-DOC-001",
            "patient_name": "Testing^Document",
            "procedure_desc": "Hasil Ekspertise Radiologi",
            "file_b64": b64_str,
            "send_to_pacs": False
        }

        response = self.client.post(
            reverse('api_doc_upload'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_API_KEY='dockey123'
        )
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertTrue(res_data.get('success'))
        self.assertEqual(res_data.get('accession_number'), 'ACSN-DOC-TEST')

        # Verifikasi record tersimpan di DocDocument (bukan Worklist)
        self.assertFalse(Worklist.objects.filter(accession_number='ACSN-DOC-TEST').exists())
        doc = DocDocument.objects.get(accession_number='ACSN-DOC-TEST')
        self.assertEqual(doc.patient_id, 'RM-DOC-001')


class CreateStudyTestCase(TestCase):
    def setUp(self):
        # Inisialisasi API Key dan user untuk pengujian API create study
        self.user = User.objects.create_user(username='studyuser', password='password123')
        self.api_key = APIKey.objects.create(name='StudyClient', key='studykey123')
        self.client = Client()

    def test_create_study_validation_missing_fields(self):
        # Pengujian validasi field wajib
        payload = {
            "accession_number": "ACC-TEST-001"
            # patient_id, patient_name, dan citra sengaja dikosongkan
        }
        res = self.client.post(
            reverse('api_study_create'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_API_KEY='studykey123'
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json().get('success'))

    def test_create_study_with_overwrite_mocked(self):
        # Pengujian alur pembuatan study dan overwrite ke Orthanc dengan simulasi mock
        from unittest.mock import patch, MagicMock

        payload = {
            "accession_number": "ACC-TEST-999",
            "patient_id": "P-999",
            "patient_name": "Testing Patient",
            "modality": "OT",
            "procedure_desc": "Foto Thorax Uji Coba",
            "image_b64": "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
            "study_id": "ST-999",
            "requesting_physician": "dr. Rad",
            "referring_physician": "dr. Refer",
            "institution_name": "RS Test",
            "other_patient_ids": "12345678"
        }

        # Mock pemanggilan HTTP ke Orthanc REST API
        with patch('bridge.views.requests.post') as mock_post, \
             patch('bridge.views.requests.delete') as mock_delete, \
             patch('bridge.views.requests.get') as mock_get:

            # 1. Mock response /tools/find (study sudah ada, kembalikan daftar ID study lama)
            mock_find_resp = MagicMock()
            mock_find_resp.status_code = 200
            mock_find_resp.json.return_value = ['old-study-uuid-111']

            # 2. Mock response /tools/create-dicom
            mock_create_resp = MagicMock()
            mock_create_resp.status_code = 200
            mock_create_resp.json.return_value = {'ID': 'new-instance-uuid-222', 'Path': '/instances/new-instance-uuid-222'}

            mock_post.side_effect = [mock_find_resp, mock_create_resp]

            # 3. Mock response DELETE /studies/{old_study_id}
            mock_del_resp = MagicMock()
            mock_del_resp.status_code = 200
            mock_delete.return_value = mock_del_resp

            # 4. Mock response GET /instances/{instance_id}
            mock_inst_resp = MagicMock()
            mock_inst_resp.status_code = 200
            mock_inst_resp.json.return_value = {
                'ParentStudy': 'new-study-uuid-333',
                'MainDicomTags': {'StudyInstanceUID': '1.2.840.113619.test.999'}
            }
            mock_get.return_value = mock_inst_resp

            res = self.client.post(
                reverse('api_study_create'),
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_API_KEY='studykey123'
            )

            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data.get('success'))
            self.assertTrue(data.get('overwritten'))
            self.assertEqual(data.get('orthanc_study_id'), 'new-study-uuid-333')
            self.assertEqual(data.get('orthanc_instance_id'), 'new-instance-uuid-222')
            self.assertEqual(data.get('study_instance_uid'), '1.2.840.113619.test.999')

            # Pastikan DELETE /studies/old-study-uuid-111 terpanggil untuk menghapus study lama
            mock_delete.assert_called_once()
            self.assertIn('old-study-uuid-111', mock_delete.call_args[0][0])

