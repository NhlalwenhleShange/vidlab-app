# VidLab — Cloud-Native Video Frame Extractor

A Flask + OpenCV service that extracts clear key frames from uploaded videos,
deployed on Azure Container Apps with automated CI/CD.

**Live**: https://app-vidlab02-prod.prouddesert-395ec443.southafricanorth.azurecontainerapps.io

## Architecture

GitHub Actions → Azure Container Registry → Azure Container Apps
                         ↓
                  Terraform-provisioned infrastructure

## Tech Stack

- Python 3.10, Flask, OpenCV, gunicorn
- Docker (python:3.10-slim base, ffmpeg for codec support)
- GitHub Actions (CI/CD)
- Azure Container Registry (image storage)
- Azure Container Apps (runtime)
- Terraform (infrastructure)

## Features

- Drag-and-drop video upload (MP4/MOV/AVI/MKV/WebM)
- Blur detection via Laplacian variance
- Two-pass frame extraction with sharpest-frame fallback
- Instant browser preview (base64-embedded JPEGs)

## Debugging Log

Real issues I hit and fixed:

1. **No frames extracted on Azure** — root cause: ffmpeg missing in
   the container image. OpenCV's ffmpeg backend wasn't available, so
   video decoding silently failed. Fix: added `ffmpeg` via apt in Dockerfile.

2. **numpy 2.x incompatibility** — `opencv-python-headless` 4.10 is
   compiled against numpy 1.x. With numpy 2.x, `cv2.VideoCapture`
   returns no frames. Fix: pinned `numpy<2` in requirements.txt.

3. **Blur threshold too strict** — videos scoring 5-9 on Laplacian
   variance were being rejected by a threshold of 40. Fix: lowered to
   4.0 and added a fallback to keep the sharpest frames anyway.

4. **Flask dev server in production** — original Dockerfile ran
   `python app.py` (dev server). Switched to gunicorn with tuned
   worker/thread counts.

## How to Run Locally

\`\`\`bash
pip install -r requirements.txt
python app.py
# Open http://localhost:8000
\`\`\`

## How to Deploy

Push to main → GitHub Actions builds and pushes to ACR →
run `az containerapp update --image ...:<sha>`
