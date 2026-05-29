# Orthanc Bridge (Orthanc Sync)

Orthanc Bridge is a premium web-based integration layer for the Orthanc PACS server, providing advanced DICOM worklist synchronization, network scanning, PACS data browsing, and node routing capabilities.

## Features

- **Dashboard**: High-level system overview, server connectivity status, and sync stats.
- **Worklist Manager**: Add, manage, and push DICOM Modality Worklists to target modalities.
- **PACS Browser (All Studies)**: Fast DICOM query/retrieve interface to search, browse, and view DICOM studies.
  - **Embedded OHIF Viewer**: Open and view DICOM studies inside a modern, embedded OHIF web viewer with proper layout adjustments.
  - **DICOM Node Transfer (C-STORE)**: Push study files to registered remote DICOM nodes dynamically.
- **DICOM Router**: Register, test connection (C-ECHO), and manage remote PACS / DICOM modalities.
- **DICOM Network Scanner**: Parallel multi-port subnet scanner to discover DICOM devices on local networks, pull Called AE Titles, and auto-register them.
- **Monitoring & API Logs**: Real-time auditing of incoming and outgoing worklist API payloads.

## Project Structure

- `bridge/`: Main Django application containing views, models, APIs, and business logic.
- `config/`: Django project settings, routing, and configurations.
- `docs/`: Technical documentation and feature walk-throughs.
- `static/`: Frontend visual assets, scripts, and styling.
- `templates/`: Django HTML templates with high-performance responsive styling.

## Detailed Documentation

For a detailed look into each module, refer to the documentation inside the [docs/](file:///d:/WebApps/orthanc-sync/docs) directory:
- [PACS Browser & OHIF Viewer Documentation](file:///d:/WebApps/orthanc-sync/docs/all_studies.md)
- [DICOM Router & Nodes Documentation](file:///d:/WebApps/orthanc-sync/docs/dicom_router.md)
- [DICOM Network Scanner Documentation](file:///d:/WebApps/orthanc-sync/docs/dicom_scanner.md)
- [Bridge Web Services API Documentation](file:///d:/WebApps/orthanc-sync/docs/bridge-api.md)

## Technical Check

Run Django system check to verify setup integrity:
```bash
python manage.py check
```
