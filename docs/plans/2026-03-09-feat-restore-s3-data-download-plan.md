---
title: Restore S3 Data Download for Astrodash
type: feat
date: 2026-03-09
---

# Restore S3 Data Download for Astrodash

## Overview

The Blast excision removed the `ObjectStore` class (`host/object_store.py`) that handled S3 downloads, leaving `initialize_data.py` unable to fetch pre-trained ML models, spectra, and user models at container startup. This plan restores that capability as a standalone astrodash utility.

## Problem Statement

When the container starts, `initialize_data.py` reads the `astrodash-data.json` manifest and finds ~1200+ missing files but only logs "Manual download required" — it never downloads anything. Django starts without ML models, making classification non-functional.

The root cause: the `ObjectStore` class from `host/object_store.py` and its `minio` dependency were removed during excision. The S3 environment variables were also stripped from `.env.default`.

## Proposed Solution

Recreate the S3 client as `astrodash/shared/object_store.py` using the `minio` library, wire it into `initialize_data.py`, and add `ASTRODASH_S3_*` environment variables.

## Implementation Phases

### Phase 1: Create `astrodash/shared/object_store.py`

Adapt the deleted `host/object_store.py` for standalone astrodash use. Strip Blast-only features (copy_directory, delete_directory, store_folder) and keep what's needed.

**New file:** `app/astrodash/shared/object_store.py`

**Required methods:**

```python
class ObjectStore:
    def __init__(self, conf: dict = {})
    # Core download/upload
    def download_object(self, path, file_path, version_id="", max_retries=5)
    def put_object(self, path, data="", file_path="", json_output=True)
    def get_object(self, path) -> bytes
    # Integrity verification
    def etag_compare(self, file_path, etag_source, file_size) -> bool
    def md5_checksum(self, file_path) -> str
    def etag_checksum(self, file_path, etag_parts, file_size) -> str
    # Listing/info
    def object_exists(self, path) -> bool
    def object_info(self, path)
    def list_directory(self, root_path, recursive=True) -> list
    def get_directory_objects(self, root_path) -> list
```

**Key changes from old code:**
- Import logger from `astrodash.shared.log` instead of `host.log`
- Default env vars use `ASTRODASH_S3_*` prefix
- Remove `initialize_bucket()` call from `__init__` — astrodash only reads from an existing bucket (add a `create_bucket` param defaulting to `False`)
- Remove Blast-only methods: `copy_directory`, `delete_directory`, `store_folder`
- Keep `stream_object` for potential future use

**Reference:** The old implementation is available via `git show 921f211^:app/host/object_store.py`

### Phase 2: Update `entrypoints/initialize_data.py`

Restore actual S3 download logic adapted from the old version.

**Modify:** `app/entrypoints/initialize_data.py`

**Changes:**
1. Add `sys.path.append` for the app directory (same pattern as old code) so `astrodash.shared` is importable from the entrypoint context
2. Import `ObjectStore` from `astrodash.shared.object_store`
3. Build S3 config dict from `ASTRODASH_S3_*` env vars
4. In `verify_data_integrity(download=True)`:
   - Initialize `ObjectStore` with the S3 config
   - For each missing file: download from `init/data/<path>` using `version_id`
   - After download (or for existing files): verify etag checksum
   - If checksum fails and `download=True`: re-download and re-verify
   - If checksum still fails: log error and `sys.exit(1)`
5. Keep the `verify` command (no download, exit on missing file)
6. Add a `manifest` command to regenerate the manifest from S3
7. Ensure parent directories are created before downloading (`os.makedirs(os.path.dirname(file_path), exist_ok=True)`)

**S3 config construction:**
```python
DATA_INIT_S3_CONF = {
    'endpoint-url': os.getenv("ASTRODASH_S3_ENDPOINT_URL", 'https://js2.jetstream-cloud.org:8001'),
    'region-name': os.getenv("ASTRODASH_S3_REGION_NAME", ''),
    'aws_access_key_id': os.getenv("ASTRODASH_S3_ACCESS_KEY_ID", ''),
    'aws_secret_access_key': os.getenv("ASTRODASH_S3_SECRET_ACCESS_KEY", ''),
    'bucket': os.getenv("ASTRODASH_S3_BUCKET", 'blast-astro-data'),
}
```

**Remove:** All Blast-specific logic (cutout/sed bucket uploads, dual app_name handling)

### Phase 3: Update dependencies and configuration

**Modify:** `app/requirements.txt`
- Add `minio` (pin to latest stable, e.g. `minio==7.2.15`)

**Modify:** `env/.env.default`
- Add S3 variables with sensible defaults:
  ```
  ASTRODASH_S3_ENDPOINT_URL = https://js2.jetstream-cloud.org:8001
  ASTRODASH_S3_REGION_NAME =
  ASTRODASH_S3_ACCESS_KEY_ID =
  ASTRODASH_S3_SECRET_ACCESS_KEY =
  ASTRODASH_S3_BUCKET = blast-astro-data
  ```
- Remove unused archive variables: `DATA_ARCHIVE_FILE`, `DATA_ARCHIVE_FILE_URL`, `USE_LOCAL_ARCHIVE_FILE`

### Phase 4: Wire upload capability for user models

The astrodash app needs to upload new user-trained models and spectra back to S3. This uses the same `ObjectStore` but with runtime S3 credentials (not init credentials).

**Modify:** `app/astrodash/config/settings.py`
- Add S3 configuration fields to the Pydantic Settings class:
  ```python
  s3_endpoint_url: str = Field("", env="ASTRODASH_S3_ENDPOINT_URL")
  s3_access_key_id: str = Field("", env="ASTRODASH_S3_ACCESS_KEY_ID")
  s3_secret_access_key: str = Field("", env="ASTRODASH_S3_SECRET_ACCESS_KEY")
  s3_region_name: str = Field("", env="ASTRODASH_S3_REGION_NAME")
  s3_bucket: str = Field("", env="ASTRODASH_S3_BUCKET")
  ```

**Modify:** Services that need upload (if any currently exist) to use `ObjectStore` from `astrodash.shared.object_store` instead of `host.object_store`. Check `astrodash/infrastructure/storage/` for any S3 references.

## Acceptance Criteria

- [x] Container starts and downloads all missing files from S3 on first boot
- [x] Existing files with matching etags are not re-downloaded
- [x] Files with mismatched etags are re-downloaded and re-verified
- [x] `python entrypoints/initialize_data.py verify` exits non-zero if files are missing
- [x] `python entrypoints/initialize_data.py download` fetches missing files and verifies checksums
- [x] `python entrypoints/initialize_data.py manifest` regenerates `astrodash-data.json` from S3
- [x] `SKIP_INITIALIZATION=true` still bypasses data init
- [x] Parent directories are created automatically for downloaded files
- [x] Download retries up to 5 times on transient failures
- [x] S3 credentials are configurable via `ASTRODASH_S3_*` env vars
- [x] `minio` is in `requirements.txt`

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `app/astrodash/shared/object_store.py` | **Create** | S3 client with download, upload, checksum verification |
| `app/entrypoints/initialize_data.py` | **Modify** | Wire ObjectStore for actual S3 downloads |
| `app/requirements.txt` | **Modify** | Add `minio` |
| `env/.env.default` | **Modify** | Add `ASTRODASH_S3_*` vars, remove archive vars |
| `app/astrodash/config/settings.py` | **Modify** | Add S3 config fields |

## Dependencies & Risks

- **S3 credentials required:** Container won't download data without valid `ASTRODASH_S3_ACCESS_KEY_ID` and `ASTRODASH_S3_SECRET_ACCESS_KEY`. The entrypoint should handle missing credentials gracefully (warn and continue, not crash).
- **First boot is slow:** ~1200 files including large PyTorch models. Consider logging a progress counter (e.g., "Downloaded 50/1200 files...").
- **Network dependency:** If the S3 endpoint is unreachable, startup will fail after retries. The `SKIP_INITIALIZATION` escape hatch exists for this.
- **Bucket naming:** Currently using `blast-astro-data` bucket. Long-term may want to copy data to an `astrodash-data` bucket, but that's out of scope for this plan.

## References

- Brainstorm: `docs/brainstorms/2026-03-09-s3-data-download-brainstorm.md`
- Deleted ObjectStore: `git show 921f211^:app/host/object_store.py`
- Deleted initialize_data.py (old): `git show 921f211^:app/entrypoints/initialize_data.py`
- Current initialize_data.py: `app/entrypoints/initialize_data.py`
- Data manifest: `app/entrypoints/astrodash-data.json`
- Docker entrypoint: `app/entrypoints/docker-entrypoint.app.sh`
- Shared utilities pattern: `app/astrodash/shared/log.py`
- Pydantic settings: `app/astrodash/config/settings.py`
