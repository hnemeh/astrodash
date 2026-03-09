# Brainstorm: Restore S3 Data Download for Astrodash

**Date:** 2026-03-09
**Status:** Ready for planning

## What We're Building

Restore the ability for astrodash containers to download pre-trained ML models, spectra, and user models from an S3-compatible endpoint at startup, and upload new data back to S3. The original download mechanism (the `ObjectStore` class in `host/object_store.py`) was deleted during the Blast excision. The data manifest (`astrodash-data.json`) and volume mounts still exist, but `initialize_data.py` currently logs "Manual download required" and never actually downloads.

## Why This Approach

- Data is still stored at the same S3-compatible endpoint (`js2.jetstream-cloud.org:8001`, bucket `blast-astro-data`)
- The `minio` Python library worked well before and the endpoint is MinIO-based
- Download + upload capability is needed (not just read-only)
- Keeping the client in `astrodash/shared/` makes it a reusable utility alongside `shared/log.py`

## Key Decisions

1. **S3 client library:** `minio` (same as Blast, proven with this endpoint)
2. **Scope:** Download at startup + upload for new user models/spectra
3. **Code location:** `astrodash/shared/object_store.py`
4. **Environment variables:** Renamed to `ASTRODASH_S3_*` pattern:
   - `ASTRODASH_S3_ENDPOINT_URL` (default: `js2.jetstream-cloud.org:8001`)
   - `ASTRODASH_S3_ACCESS_KEY_ID`
   - `ASTRODASH_S3_SECRET_ACCESS_KEY`
   - `ASTRODASH_S3_REGION_NAME`
   - `ASTRODASH_S3_BUCKET` (default: `blast-astro-data`)
5. **Manifest:** Continue using `astrodash-data.json` with version_id and etag verification
6. **Initialization:** `initialize_data.py` calls the new object store client to download missing files

## Components Affected

- **New:** `app/astrodash/shared/object_store.py` — S3 client with download/upload/etag verification
- **Modified:** `app/entrypoints/initialize_data.py` — Wire up actual S3 downloads
- **Modified:** `app/requirements.txt` — Add `minio` package
- **Modified:** `env/.env.default` — Add `ASTRODASH_S3_*` variables
- **Cleanup:** Remove unused `DATA_ARCHIVE_FILE*` and `USE_LOCAL_ARCHIVE_FILE` env vars

## Open Questions

- Should download failures be fatal (exit container) or allow degraded startup?
- Should we add a progress indicator for the initial download (potentially GB of data)?
- Is the `blast-astro-data` bucket name acceptable long-term, or should data be copied to an `astrodash-data` bucket?
