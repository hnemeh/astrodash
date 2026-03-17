---
title: "feat: Reduce Docker Image Size"
type: feat
status: active
date: 2026-03-16
origin: docs/brainstorms/2026-03-16-reduce-docker-image-size-brainstorm.md
---

# feat: Reduce Docker Image Size

## Acceptance Criteria

- [x] Image size reduced from ~9GB to ~3GB or less (achieved 1.82GB — 80% reduction)
- [ ] All application functionality preserved
- [ ] CPU-only PyTorch inference works correctly
- [x] Image builds successfully

## MVP

### app/Dockerfile

- Switch both stages to `python:3.11-slim`
- Install build dependencies (gcc, etc.) in the deps stage only
- Install torch and torchvision from CPU-only index

### app/requirements.txt

- Remove `torch` and `torchvision` from main requirements (install separately in Dockerfile with CPU-only index)

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-03-16-reduce-docker-image-size-brainstorm.md](docs/brainstorms/2026-03-16-reduce-docker-image-size-brainstorm.md)
- **Dockerfile:** `app/Dockerfile`
- **Requirements:** `app/requirements.txt`
