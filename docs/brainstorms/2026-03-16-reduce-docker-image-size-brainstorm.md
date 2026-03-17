# Brainstorm: Reduce Docker Image Size

**Date:** 2026-03-16
**Status:** Ready for planning

## What We're Building

Reduce the astrodash Docker image from ~9GB to ~3GB without removing any functionality. The large image causes disk pressure on Kubernetes worker nodes and slow pull times.

## Why This Approach

**Chosen: CPU-only PyTorch + python:3.11-slim base image**

The two biggest size contributors are:
1. **PyTorch with CUDA** (~2.5GB) — the app auto-detects GPU availability and falls back to CPU. The Jetstream2 cluster has no GPUs, so CUDA libraries are dead weight.
2. **Full python:3.11 base image** (~1GB) — includes build tools, compilers, and documentation not needed at runtime.

Switching to CPU-only PyTorch variants and the slim base image saves ~5-6GB with zero functionality loss.

**Rejected alternatives:**
- **Alpine base:** musl libc breaks scientific Python packages (numpy, scipy, torch). Not practical.
- **Distroless:** Complex to get right with native extensions. Fragile build process.

## Key Decisions

- **Base image:** `python:3.11-slim` (both build and runtime stages)
- **PyTorch:** Install CPU-only variant via `--index-url https://download.pytorch.org/whl/cpu`
- **torchvision:** Same CPU-only index
- **System deps:** The slim image may need `apt-get install` for some build dependencies in the deps stage (gcc, etc.) but the runtime stage stays minimal
- **No functionality removed:** All features preserved, GPU auto-detection still works (just won't find a GPU)

## Resolved Questions

- **GPU usage:** Code uses `torch.device('cuda' if torch.cuda.is_available() else 'cpu')` — GPU-optional. CPU-only is fine.
- **Expected size:** ~9GB → ~3GB (estimated)
