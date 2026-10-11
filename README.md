# VidLab — Cloud-Native Video Frame Extractor

A Flask + OpenCV service that extracts sharp key frames from uploaded
videos. Deployed on Azure Container Apps with a GitHub Actions CI/CD
pipeline that publishes Docker images to Azure Container Registry.

**Live demo**: [app-vidlab02-prod.prouddesert-395ec443.southafricanorth.azurecontainerapps.io](https://app-vidlab02-prod.prouddesert-395ec443.southafricanorth.azurecontainerapps.io)

**Infrastructure repo**: [github.com/NhlalwenhleShange/terraform-vidlab-infrastructure](https://github.com/NhlalwenhleShange/terraform-vidlab-infrastructure)

---

## What it does

Upload a video, get back the crispest frames from across its duration.
Blur detection filters out soft or motion-heavy shots, and a fallback
guarantees results even from compressed or low-light footage.

### How it works

1. **Sampling** — one frame per second is decoded across the full video
   duration, regardless of codec or length.
2. **Scoring** — each sampled frame is scored by Laplacian variance, a
   measure of high-frequency edge energy that approximates sharpness.
3. **Selection** — frames above the blur threshold are kept up to a limit
   of 15. If none pass, the sharpest available frames are returned
   instead, so the service never returns an empty result for a readable
   video.

Supported formats: MP4, MOV, AVI, MKV, WebM · up to 200 MB.

---

## Architecture
