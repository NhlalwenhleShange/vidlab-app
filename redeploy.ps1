# redeploy.ps1 — deploy the latest pushed image to Container Apps
$ErrorActionPreference = "Stop"

$APP = "app-vidlab02-prod"
$RG  = "rg-vidlab02-prod"
$ACR = "vidlab02acrprod01"
$IMG = "vidlab-app"

# Ensure repo is clean
$status = git status --porcelain
if ($status) {
    Write-Host "⚠️  Uncommitted changes. Commit and push first:" -ForegroundColor Yellow
    Write-Host $status
    exit 1
}

$TAG = (git rev-parse --short HEAD).Trim()
$IMAGE = "$ACR.azurecr.io/${IMG}:$TAG"

Write-Host "🎯 Target: $IMAGE" -ForegroundColor Cyan

# Verify the image was actually pushed by CI
$tags = az acr repository show-tags --name $ACR --repository $IMG -o tsv
if ($tags -notcontains $TAG) {
    Write-Host "❌ Tag '$TAG' not in ACR yet." -ForegroundColor Red
    Write-Host "The GitHub Action may still be running. Check:" -ForegroundColor Yellow
    Write-Host "https://github.com/NhlalwenhleShange/vidlab-app/actions" -ForegroundColor Gray
    exit 1
}

# Deploy
az containerapp update --name $APP --resource-group $RG --image $IMAGE

# Confirm
az containerapp show --name $APP --resource-group $RG `
  --query "{image:properties.template.containers[0].image, state:properties.provisioningState}" `
  -o table