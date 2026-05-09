param(
  [string]$HostName = "194.87.243.63",
  [string]$UserName = "root",
  [string]$RemoteDir = "/opt/era-media-factory",
  [string]$BackendPort = "18000",
  [string]$FrontendPort = "13000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Archive = Join-Path $Root "era-media-factory.tar.gz"

Write-Host "== ERA Media Factory safe deploy =="
Write-Host "Project: $Root"
Write-Host "Server:  $UserName@$HostName"
Write-Host "Remote:  $RemoteDir"
Write-Host ""

Push-Location $Root
try {
  Write-Host "Building archive..."
  tar --exclude='frontend/node_modules' `
      --exclude='.git' `
      --exclude='era-media-factory.tar.gz' `
      --exclude='frontend/.next' `
      --exclude='.tmp' `
      --exclude='.pip-cache' `
      --exclude='.npm-cache' `
      --exclude='.ssh' `
      -czf era-media-factory.tar.gz .
} finally {
  Pop-Location
}

Write-Host "Uploading archive..."
scp $Archive "${UserName}@${HostName}:/tmp/era-media-factory.tar.gz"

$ComposeEnv = "BACKEND_PORT=$BackendPort FRONTEND_PORT=$FrontendPort DEV_MODE=true BACKEND_CORS_ORIGINS=http://localhost:$FrontendPort,http://$HostName`:$FrontendPort"
$RemoteCommand = @"
set -e
mkdir -p $RemoteDir
cd $RemoteDir
find . -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} +
tar -xzf /tmp/era-media-factory.tar.gz -C $RemoteDir
$ComposeEnv docker compose up --build -d
for i in `$(seq 1 60); do curl -fsS http://localhost:$BackendPort/health && break; sleep 2; done
for i in `$(seq 1 60); do curl -fsS http://localhost:$FrontendPort/api/status && break; sleep 2; done
$ComposeEnv docker compose exec -T backend python -m app.smoke_control_plane
curl -fsS http://localhost:$FrontendPort/api/operating-loop/latest || true
echo
echo "DEPLOY OK: http://$HostName`:$FrontendPort"
"@

Write-Host "Deploying on server..."
ssh "${UserName}@${HostName}" $RemoteCommand
