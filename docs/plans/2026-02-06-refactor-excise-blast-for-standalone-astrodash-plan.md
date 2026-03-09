---
title: "Excise Blast Code for Standalone Astrodash Repository"
type: refactor
date: 2026-02-06
---

# Excise Blast Code for Standalone Astrodash Repository

## Overview

Surgically remove all Blast-specific code from the shared repository on the
`feature/astrodash_excise` branch, leaving a standalone Django application for Astrodash.
The result will be moved to its own GitHub repository. Blast will be reverted to a branch
without Astrodash code.

## Problem Statement / Motivation

Blast and Astrodash are fundamentally different astrophysics applications sharing a single
repository. Blast focuses on automated transient host galaxy characterization (SED fitting,
photometry, cutouts). Astrodash focuses on ML-based supernova spectrum classification. Their
expected evolution paths diverge significantly, and sharing a repository creates unnecessary
coupling and complexity.

## Research Findings

### Confirmed Clean Boundaries

- **No cross-model ForeignKeys**: Astrodash models have zero ForeignKey/ManyToMany
  relationships to host models. The database schemas are fully independent.
- **No code imports**: Astrodash code (`/app/astrodash/`) has zero imports from `host` or `api`.
- **No shared static assets**: Astrodash templates do not reference host static files.
- **No MinIO usage**: Astrodash uses form-based FileFields (in-memory), not object storage.

### Identified Dependencies Requiring Resolution

1. **Template inheritance**: `astrodash/templates/astrodash/base.html` extends `host/base.html`
   (`app/astrodash/templates/astrodash/base.html:1`)
2. **Users template**: `users/templates/registration/login.html` extends `host/base.html`
   (`app/users/templates/registration/login.html:1`)
3. **Logging utility**: `host/log.py` is imported by `app/auth_backend.py:13` and
   `users/context_processors.py:4` — trivial `get_logger()` wrapper
4. **Template tags**: `host/templatetags/host_tags.py` provides `app_version` and
   `support_email` tags used in `host/base.html` and `users/login.html`
5. **Context processor**: `users/context_processors.py:39-40` checks Blast-specific
   permissions (`host.retrigger_transient`, `host.reprocess_transient`)
6. **Settings references**: `CELERY_IMPORTS` lists `host.tasks`, `host.system_tasks`,
   `host.transient_tasks` (`app/settings.py:216-220`)
7. **URL error handlers**: `handler403` and `handler404` point to `host.views`
   (`app/urls.py:30-31`)
8. **Entrypoints**: Multiple scripts import from `host` for data initialization and
   periodic task setup

## Proposed Solution

### Architecture

Perform surgical removal in 6 ordered phases. Each phase is independently testable.
The Django project directory is renamed from `app/app/` to `app/astrodash_project/` to
avoid confusion with the `app/astrodash/` Django app.

> **Naming convention**: The Django *project* (settings, urls, wsgi, asgi) becomes
> `astrodash_project`. The Django *app* remains `astrodash`. This avoids a naming collision
> where both the project directory and the app directory would be called `astrodash`.

### Implementation Phases

---

#### Phase 1: Resolve Template and Utility Dependencies

Before removing anything, create standalone replacements for the shared pieces that
Astrodash and users depend on.

**1.1 Create standalone base template**

Create `app/astrodash/templates/astrodash/standalone_base.html` (then rename to `base_site.html`
or similar) by copying `host/base.html` and adapting it:

- Remove `{% load latexify %}` and `{% load host_tags %}`
- Remove Blast-specific navigation (transient_list, add_transient, blast_logo)
- Replace with Astrodash navigation (classify, batch, landing page)
- Update branding: logo, colors, footer links, support email
- Update docs link from blast.readthedocs.io to astrodash docs
- Keep Bootstrap 4, Bokeh, jQuery includes
- Load new `astrodash_tags` instead of `host_tags`

**1.2 Update astrodash/base.html**

Change `{% extends "host/base.html" %}` to `{% extends "astrodash/base_site.html" %}`
at `app/astrodash/templates/astrodash/base.html:1`.

**1.3 Update users/login.html**

Change `{% extends 'host/base.html' %}` to `{% extends 'astrodash/base_site.html' %}`
and `{% load host_tags %}` to `{% load astrodash_tags %}`
at `app/users/templates/registration/login.html:1-2`.

Also update Blast-specific text content (e.g., "Blast administrator" on line 89,
"Blast support" on lines 108/110/121).

**1.4 Create astrodash template tags**

Create `app/astrodash/templatetags/astrodash_tags.py` with the `app_version` and
`support_email` tags copied from `app/host/templatetags/host_tags.py`. These are simple
wrappers around `settings.APP_VERSION` and `settings.SUPPORT_EMAIL`.

Also create `app/astrodash/templatetags/__init__.py`.

**1.5 Move logging utility**

Create `app/astrodash/shared/log.py` (or inline into the project) with the `get_logger()`
function from `app/host/log.py:5-12`. Update imports in:

- `app/app/auth_backend.py:13` — change `from host.log import get_logger` to new location
- `app/users/context_processors.py:4` — same change

**1.6 Fix users/context_processors.py**

Remove Blast-specific permission checks at `app/users/context_processors.py:39-40`:
```python
'has_perm_retrigger_transient': check_perms(user, "host.retrigger_transient"),
'has_perm_reprocess_transient': check_perms(user, "host.reprocess_transient"),
```
These are Blast-specific permissions that Astrodash doesn't need.

**Files modified:**
- `app/astrodash/templates/astrodash/base_site.html` (NEW)
- `app/astrodash/templates/astrodash/base.html`
- `app/users/templates/registration/login.html`
- `app/astrodash/templatetags/__init__.py` (NEW)
- `app/astrodash/templatetags/astrodash_tags.py` (NEW)
- `app/astrodash/shared/log.py` (NEW — or place elsewhere)
- `app/app/auth_backend.py`
- `app/users/context_processors.py`

---

#### Phase 2: Remove Blast-Specific Directories

Delete the following directories entirely:

- `app/host/` — Blast transient/host galaxy analysis (91 files, 38 migrations)
- `app/api/` — Blast REST API (serializers, views, components)
- `batch/` — Blast batch processing scripts
- `data/` — Blast data directories (cutout_cdn, sed_output, sbipp, transmission)
- `validation/` — Blast validation scripts and data
- `dash/` — Old React/NodeJS Astrodash (superseded)
- `app/debug/` — Debug utilities that import from host

**Files removed:** ~200+ files across 7 directories

---

#### Phase 3: Rename Django Project and Update Configuration

**3.1 Rename project directory**

Rename `app/app/` to `app/astrodash_project/`. This directory contains:
- `settings.py`
- `urls.py`
- `wsgi.py`
- `asgi.py`
- `celery.py`
- `auth_backend.py`
- `__init__.py`

**3.2 Update settings.py** (`app/astrodash_project/settings.py`)

Remove from `INSTALLED_APPS`:
- `"host"` (line 59)
- `"api"` (line 67)
- `"latexify"` (line 76) — only used by host base template

Consider removing if not needed by Astrodash:
- `"revproxy"` (line 65) — check if Astrodash uses it
- `"django_cron"` (line 71) — check if Astrodash uses it

Update `ROOT_URLCONF`:
- `"app.urls"` → `"astrodash_project.urls"` (line 91)

Update `WSGI_APPLICATION`:
- `"app.wsgi.application"` → `"astrodash_project.wsgi.application"` (line 113)

Update `TEMPLATES["DIRS"]`:
- Remove `os.path.join(BASE_DIR, "host", "templates", "host")` (line 97)

Update database defaults:
- `'NAME': os.getenv('DB_NAME', 'blast')` → `os.getenv('DB_NAME', 'astrodash')` (line 123)
- `'USER': os.getenv('DB_USER', 'blast')` → `os.getenv('DB_USER', 'astrodash')` (line 124)

Remove Blast-specific settings (lines 175-195):
- `MEDIA_URL`, `MEDIA_ROOT` (Blast cutout paths)
- `DUSTMAPS_DATA_ROOT`, `CUTOUT_ROOT`, `SED_OUTPUT_ROOT`, `SBI_TRAINING_ROOT`
- `PROST_OUTPUT_ROOT`, `TNS_STAGING_ROOT`, `TNS_INGEST_TIMEOUT`, `TNS_SIMULATE`
- `SBIPP_ROOT`, `SBIPP_PHOT_ROOT`, `TRANSMISSION_CURVES_ROOT`
- `CUTOUT_OVERWRITE`
- `JOB_SCRATCH_MAX_SIZE`, `JOB_SCRATCH_FREE_SPACE`
- `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_BASE_PATH`, `S3_LOGS_PATH`
- `USAGE_METRICS_*` settings

Remove Blast Celery imports (lines 216-220):
```python
CELERY_IMPORTS = [
    "host.tasks",
    "host.system_tasks",
    "host.transient_tasks",
]
```
Replace with empty list or Astrodash task imports if applicable.

Remove Blast Celery task routes (lines 249-252):
```python
CELERY_TASK_ROUTES = {
    'Global Host SED Fitting': {'queue': 'sed'},
    'Local Host SED Fitting': {'queue': 'sed'},
}
```

Update `AUTHENTICATION_BACKENDS`:
- `'app.auth_backend.CustomOIDCAuthenticationBackend'` →
  `'astrodash_project.auth_backend.CustomOIDCAuthenticationBackend'` (line 145)

Update `OIDC_OP_LOGOUT_URL_METHOD`:
- `"app.auth_backend.execute_logout"` → `"astrodash_project.auth_backend.execute_logout"` (line 274)

Update `LOGIN_REDIRECT_URL`:
- `"/add"` → `"/astrodash/"` (line 278) — `/add` is a Blast route

**3.3 Update urls.py** (`app/astrodash_project/urls.py`)

Remove:
- `path("", include("host.urls"))` (line 22)
- `path("api/", include("api.urls"))` (line 23)
- `handler403 = "host.views.error_view"` (line 30)
- `handler404 = "host.views.resource_not_found_view"` (line 31)

Update Astrodash to be the root:
- Consider `path("", include("astrodash.urls"))` to serve Astrodash at root
- Or keep `path("astrodash/", ...)` — design choice

Remove error handlers (use Django defaults) or create simple Astrodash error views.

**3.4 Update wsgi.py**

Change `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")` to
`os.environ.setdefault("DJANGO_SETTINGS_MODULE", "astrodash_project.settings")`

**3.5 Update asgi.py**

Same change as wsgi.py.

**3.6 Update manage.py**

Change `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")` to
`os.environ.setdefault("DJANGO_SETTINGS_MODULE", "astrodash_project.settings")`

**3.7 Update celery.py**

Change `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")` to
`os.environ.setdefault("DJANGO_SETTINGS_MODULE", "astrodash_project.settings")`

Also update the Celery app name if desired:
`app = Celery("app")` → `app = Celery("astrodash")`

**3.8 Update auth_backend.py**

Already handled in Phase 1 (log import). Verify no other `app.` references remain.

**Files modified:**
- `app/app/` → `app/astrodash_project/` (directory rename)
- `app/astrodash_project/settings.py`
- `app/astrodash_project/urls.py`
- `app/astrodash_project/wsgi.py`
- `app/astrodash_project/asgi.py`
- `app/astrodash_project/celery.py`
- `app/manage.py`

---

#### Phase 4: Update Docker, DevOps, and Environment

**4.1 Dockerfile** (`app/Dockerfile`)

Remove Blast-specific system packages (lines 14-25):
- `libhealpix-cxx-dev`, `libhdf5-dev`, `libnetcdf-dev`, `libcfitsio-dev` etc.
  — audit which are needed by Astrodash's PyTorch and scientific dependencies

Update `DJANGO_SETTINGS_MODULE` if set anywhere.

Remove MinIO client install if not needed.

**4.2 Docker Compose files**

For each compose file (`docker-compose.yml`, `docker-compose.dev.yaml`,
`docker-compose.prod.yaml`, `docker-compose.ci.yaml`):

- Rename project: `name: blast-*` → `name: astrodash-*`
- Rename volumes: `blast-db` → `astrodash-db`, `blast-data` → remove (Blast-specific)
- Keep `astrodash-data` volume
- Remove `batch` service (Blast-specific)
- Update image references: `BLAST_IMAGE` → `ASTRODASH_IMAGE`
- Update `DJANGO_SETTINGS_MODULE` env vars if set
- Review object-store (MinIO) service — remove if Astrodash doesn't use it,
  or keep if it's used for astrodash-data

**4.3 Rename blastctl**

- Rename `run/blastctl` → `run/astrodashctl`
- Update all internal references:
  - `COMPOSE_PROJECT_NAME="blast-dev"` → `"astrodash-dev"` (and prod, ci variants)
  - Volume names in purge commands

**4.4 Update get_compose_args.sh**

- Update volume names: `blast_blast-db` → `astrodash_astrodash-db` etc.
- Update project name defaults

**4.5 Update test script**

- `run/blast.test.sh` → `run/astrodash.test.sh`
- Remove `host.tests`, `api.tests` from test module list

**4.6 Update environment files**

For `env/.env.default` and `env/.env.dev`:

- `DB_NAME = blast_db` → `astrodash_db`
- `DB_USER = blast` → `astrodash`
- Remove `BLAST_IMAGE`, add `ASTRODASH_IMAGE`
- Remove `OUTPUT_DIR = /tmp/blast_results`
- Remove all Blast data directory env vars (DUSTMAPS, CUTOUT, SED, TNS, SBIPP, etc.)
- Remove Blast-specific S3 paths
- Update `DATA_ARCHIVE_FILE_URL` to Astrodash data URL
- Keep OIDC, Redis, Django settings

**4.7 Update nginx configuration**

`nginx/default.conf` and `nginx/default_slim.conf`:
- These are generic proxy configs — minimal changes needed
- Update any Blast-specific comments or server names

**4.8 Update entrypoints**

`app/entrypoints/docker-entrypoint.app.sh`:
- Remove `bash entrypoints/initialize_data_dirs.sh` call (Blast data dirs)
- Update `DJANGO_SETTINGS_MODULE` reference
- Remove `host.tests api.tests` from test module list
- Keep `astrodash` test references

`app/entrypoints/docker-entrypoint.celery.sh`:
- Remove `bash entrypoints/initialize_data_dirs.sh`
- Update settings module reference

`app/entrypoints/docker-entrypoint.celery_beat.sh`:
- Same changes as celery.sh

`app/entrypoints/initialize_data_dirs.sh`:
- **Remove entirely** — creates Blast-specific data directory symlinks

`app/entrypoints/initialize_data.py`:
- Remove all Blast data download/upload logic (lines 104-132)
- Keep Astrodash data initialization (line 136)
- Remove `from host.object_store import ObjectStore` and `from host.log import get_logger`
- Replace with standard logging

`app/entrypoints/setup_initial_periodic_tasks.py`:
- **Remove entirely** or gut — imports `host.tasks` and `host.views`
- Replace with Astrodash periodic task setup if needed

`app/init_app.py`:
- Remove call to `setup_initial_periodic_tasks.py` (line 30-32)
- Keep fixture loading and superuser setup

`app/entrypoints/load_example_data.sh`:
- Review — currently loads fixtures from all apps

**Files modified/removed:**
- `app/Dockerfile`
- `docker/docker-compose.yml`
- `docker/docker-compose.dev.yaml`
- `docker/docker-compose.prod.yaml`
- `docker/docker-compose.ci.yaml`
- `run/blastctl` → `run/astrodashctl` (rename + modify)
- `run/get_compose_args.sh`
- `run/blast.test.sh` → `run/astrodash.test.sh`
- `env/.env.default`
- `env/.env.dev`
- `nginx/default.conf` (minor)
- `nginx/default_slim.conf` (minor)
- `app/entrypoints/docker-entrypoint.app.sh`
- `app/entrypoints/docker-entrypoint.celery.sh`
- `app/entrypoints/docker-entrypoint.celery_beat.sh`
- `app/entrypoints/initialize_data_dirs.sh` (REMOVE)
- `app/entrypoints/initialize_data.py`
- `app/entrypoints/setup_initial_periodic_tasks.py` (REMOVE or gut)
- `app/init_app.py`

---

#### Phase 5: Clean Up Dependencies and Requirements

**5.1 Audit and trim requirements.txt**

Remove Blast-specific packages from `app/requirements.txt`:
- `astro-datalab` — Blast data lab queries
- `astro-prospector` — Blast SED fitting
- `astro-prost` — Blast PROST SED fitting
- `astro-sedpy` — Blast SED fitting
- `dustmaps` — Blast dust correction
- `dynesty` — Blast SED fitting sampler
- `extinction` — Blast extinction correction
- `fsps` — Blast stellar population synthesis
- `mysqlclient` — Legacy (migrated to PostgreSQL)
- `sbi` — Blast simulation-based inference

Packages to **verify** before removing (may have Astrodash dependencies):
- `torch`, `torchvision` — Astrodash uses PyTorch for ML classification. **KEEP**.
- `astroquery` — Check if Astrodash uses it
- `bokeh` — Used in Astrodash templates. **KEEP**.
- `photutils` — Check if Astrodash uses it
- `latexify-py` — Removed from INSTALLED_APPS, check if used elsewhere

Run `pip check` after removal to verify no broken transitive dependencies.

**5.2 Audit for stale references**

After all removals, perform a comprehensive grep for leftover references:
```
grep -r "host\." app/ --include="*.py"
grep -r "blast" . --include="*.py" --include="*.yaml" --include="*.yml" --include="*.sh" --include="*.conf" --include="*.env"
grep -r "from api" app/ --include="*.py"
```

**Files modified:**
- `app/requirements.txt`

---

#### Phase 6: Documentation, CI/CD, and Metadata

**6.1 Update README.md**

Replace Blast content with Astrodash description, badges, and links.

**6.2 Reset CHANGELOG.md**

Start fresh with a note: "Forked from Blast repository. See [Blast CHANGELOG] for prior history."

**6.3 Update CONTRIBUTING.md**

Replace Blast references with Astrodash.

**6.4 Update docs/ (Sphinx)**

- `docs/conf.py`: Change `project = "Blast"` → `"Astrodash"`, update copyright
- `docs/index.rst`: Replace Blast content with Astrodash overview
- Remove Blast-specific doc pages (SED params, batch processing, etc.)
- Add placeholder pages for Astrodash features (classification, batch, API)
- Keep developer guide structure but update content

**6.5 Update .readthedocs.yml**

Update requirements path if project directory changed.

**6.6 Update GitHub workflows**

`.github/workflows/docker_image_workflow.yml`:
- Update `DOCKER_IMAGE` from Blast registry to Astrodash registry
- Update `blastctl` → `astrodashctl` reference
- Update test commands

Review and update any other workflow files.

**6.7 Update GitHub templates**

Update issue templates and PR template to reference Astrodash instead of Blast.

**6.8 Update .gitignore**

Review for Blast-specific entries.

**6.9 Update LICENSE**

Verify license is still appropriate; update copyright if needed.

**Files modified:**
- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `docs/conf.py`
- `docs/index.rst`
- Various `docs/*.rst` files
- `.readthedocs.yml`
- `.github/workflows/*.yml`
- `.github/ISSUE_TEMPLATE/*`
- `.github/PULL_REQUEST_TEMPLATE.md`

---

## Database Migration Notes

### Fresh Deployments

No special handling needed. Django will run only Astrodash and users migrations.

### Existing Deployments (Running Both Blast + Astrodash)

If migrating an existing deployment:

1. **Back up the database** before any changes
2. **Clean Celery Beat schedules**: Remove periodic tasks referencing `host.*`:
   ```sql
   DELETE FROM django_celery_beat_periodictask WHERE task LIKE 'host.%';
   ```
3. **Clean orphaned migration records** (optional but tidy):
   ```sql
   DELETE FROM django_migrations WHERE app IN ('host', 'api');
   ```
4. **Clean orphaned permissions**:
   ```sql
   DELETE FROM auth_permission WHERE content_type_id IN (
     SELECT id FROM django_content_type WHERE app_label IN ('host', 'api')
   );
   DELETE FROM django_content_type WHERE app_label IN ('host', 'api');
   ```
5. Blast tables (host_*, api_*) can be dropped or left in place — Django won't touch them.

## Acceptance Criteria

### Functional Requirements

- [ ] Astrodash web UI loads at configured URL path with proper navigation
- [ ] Astrodash API endpoints respond correctly at `/astrodash/api/v1/`
- [ ] Spectrum classification works end-to-end
- [ ] Batch processing works
- [ ] User login/logout via OIDC works
- [ ] Login page renders with Astrodash branding
- [ ] Error pages (404, 403) render without crashing
- [ ] Celery workers start without import errors
- [ ] Django admin panel accessible

### Non-Functional Requirements

- [ ] `python manage.py check` passes with no errors
- [ ] `python manage.py migrate` runs cleanly on fresh database
- [ ] Docker image builds successfully
- [ ] All containers start via `astrodashctl full_dev up`
- [ ] No references to `host`, `blast`, or `api` remain in Python code
  (excluding comments, documentation, and git history)
- [ ] `requirements.txt` contains no Blast-specific packages
- [ ] `grep -r "from host" app/ --include="*.py"` returns zero results

### Quality Gates

- [ ] Application test suite passes
- [ ] Docker compose stack starts cleanly with all services healthy

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Missed `host` reference causes runtime crash | Medium | High | Comprehensive grep audit in Phase 5.2 |
| Template rendering broken | Low | High | Phase 1 resolves all template dependencies before removal |
| Celery worker crashes on orphaned DB tasks | Medium | Medium | Clean Celery Beat schedules (documented in migration notes) |
| Missing Python package breaks import | Low | Medium | Run `pip check` and full test suite after requirement trim |
| Docker build fails from missing system libs | Low | Medium | Build and test image after Dockerfile changes |

## References

### Internal

- Brainstorm: `docs/brainstorms/2026-02-06-astrodash-excision-brainstorm.md`
- Astrodash app: `app/astrodash/` (75 files, domain-driven architecture)
- Blast host app: `app/host/` (91 files — to be removed)
- Django settings: `app/app/settings.py`
- Docker compose: `docker/docker-compose.yml`
- Control script: `run/blastctl`
- Template dependency: `app/astrodash/templates/astrodash/base.html:1` extends `host/base.html`
- Auth backend host coupling: `app/app/auth_backend.py:13`
- Users host coupling: `app/users/context_processors.py:4,39-40`
