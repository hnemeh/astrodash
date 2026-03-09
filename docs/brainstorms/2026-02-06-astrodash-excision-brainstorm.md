# Brainstorm: Excise Blast Code to Create Standalone Astrodash Repository

**Date:** 2026-02-06
**Status:** Decided
**Branch:** feature/astrodash_excise

## What We're Building

A standalone Astrodash repository by surgically removing all Blast-specific code from the
current shared repository. The goal is to separate two fundamentally different astrophysics
applications (Blast and Astrodash) that are expected to evolve independently. Blast will
be reverted to a branch without Astrodash code. The shared infrastructure patterns
(migrations, docker setup, devops scripts) will be preserved but adapted for Astrodash only.

## Why This Approach

**Approach chosen: Surgical Removal in Place (Approach A)**

Work in the `feature/astrodash_excise` branch, systematically removing Blast-specific code
and renaming/adapting shared infrastructure. This was chosen over starting a fresh repo
because it:

- Preserves git history for shared code and Astrodash-specific code
- Maintains the proven infrastructure patterns (docker, migrations, entrypoints)
- Is incremental and trackable
- Reduces risk of missing shared infrastructure nuances

## Key Decisions

### 1. Directories to Remove (Blast-specific)
- `/app/host/` — Blast transient/host galaxy analysis (91 files, 38 migrations)
- `/app/api/` — REST API primarily for Blast
- `/batch/` — Blast batch processing scripts
- `/data/` — Blast data (cutouts, SED output, transmission)
- `/validation/` — Blast validation scripts and data
- `/dash/` — Old React/NodeJS Astrodash (superseded)

### 2. Directories to Keep and Adapt
- `/app/astrodash/` — Core Astrodash application (keep as-is)
- `/app/users/` — Authentication and user profiles (keep, including OIDC)
- `/app/app/` → Rename project to `astrodash` — Update settings.py, urls.py, wsgi.py, asgi.py
- `/docker/` — Keep and rebrand (remove Blast-specific services like batch container)
- `/run/` — Rename `blastctl` → `astrodashctl`, adapt scripts
- `/nginx/` — Adapt proxy configs for Astrodash-only routing
- `/env/` — Clean environment files of Blast-specific variables
- `/docs/` — Keep Sphinx/ReadTheDocs structure, gut Blast content, add Astrodash placeholders
- `/.github/` — Keep and adapt CI/CD workflows, issue/PR templates for Astrodash
- `/app/entrypoints/` — Keep initialization scripts, remove Blast fixture loading

### 3. Django Project Renaming
- Rename the Django project from `app` to `astrodash`
- Update all references: `app.settings` → `astrodash.settings`, etc.
- Update `INSTALLED_APPS` to remove `host`, `api`
- Update `urls.py` to only route Astrodash and users

### 4. DevOps Rebranding
- `blastctl` → `astrodashctl`
- Docker compose profiles adapted for Astrodash
- Keep Celery (worker, beat, flower) — Astrodash uses it for batch processing
- Remove batch container service (Blast-specific)
- Keep PostgreSQL, Redis, Nginx, MinIO

### 5. Dependencies
- Clean `requirements.txt` to remove Blast-specific packages
  (Prospector, PROST, TNS client, astronomical photometry libs, etc.)
- Keep: Django, DRF, Celery, Redis, PyTorch, OIDC, Pydantic, etc.

### 6. Authentication
- Keep the full `/app/users/` app including OIDC integration

### 7. Data Handling
- Astrodash uses `/mnt/astrodash-data/` (mounted volume) — not the repo's `/data/` dir
- No changes needed to Astrodash's data path configuration

### 8. Future Consideration (Not Now)
- Shared code could eventually be extracted into a platform/module repo
- For now, accept that Blast and Astrodash repos may diverge on shared patterns

## Open Questions

- Exact list of Python packages to remove from requirements (need to audit imports)
- Whether any GitHub Actions workflows reference Blast-specific test suites or deploy targets
- Whether the `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE` need updates
  (likely yes — at minimum README and CHANGELOG)

## Scope of Work (High-Level Steps)

1. Remove Blast-specific directories (`host`, `api`, `batch`, `data`, `validation`, `dash`)
2. Rename Django project `app` → `astrodash` (settings, urls, wsgi, asgi, manage.py)
3. Update `INSTALLED_APPS` and URL configuration
4. Rebrand devops: `blastctl` → `astrodashctl`, update docker-compose files
5. Adapt nginx configuration for Astrodash-only routing
6. Clean environment files of Blast-specific variables
7. Audit and trim `requirements.txt`
8. Update entrypoints (remove Blast fixture loading, adapt initialization)
9. Gut docs content, add Astrodash placeholders
10. Adapt CI/CD workflows and GitHub templates
11. Update README, CHANGELOG, CONTRIBUTING
12. Test that the resulting application builds and runs
