# ============================================================
# Railway Auto-Setup Script for Sapphire Discord Bot
# ============================================================
# INSTRUKSI:
# 1. Buka https://railway.com/account/tokens
# 2. Klik "Create Token", beri nama "deploy-bot"
# 3. Salin token-nya
# 4. Jalankan script ini dengan: .\setup_railway.ps1
# ============================================================

$RAILWAY_TOKEN = Read-Host "Masukkan Railway API Token Anda"
$PROJECT_ID = "772f896a-4a6d-4b51-b4ec-595feb330648"
$API = "https://backboard.railway.com/graphql/v2"

$headers = @{
    "Authorization" = "Bearer $RAILWAY_TOKEN"
    "Content-Type"  = "application/json"
}

function Invoke-RailwayAPI($query, $variables = @{}) {
    $body = @{ query = $query; variables = $variables } | ConvertTo-Json -Depth 10
    $response = Invoke-RestMethod -Uri $API -Method Post -Headers $headers -Body $body
    return $response
}

Write-Host "`n[1/6] Mengambil info project..." -ForegroundColor Cyan
$projectQuery = @"
query { 
  project(id: "$PROJECT_ID") { 
    id 
    name 
    services { edges { node { id name } } }
  } 
}
"@
$projectData = Invoke-RailwayAPI $projectQuery
$projectName = $projectData.data.project.name
$services = $projectData.data.project.services.edges
Write-Host "  Project: $projectName" -ForegroundColor Green
Write-Host "  Services: $($services.Count)" -ForegroundColor Green

# Cari service ID yang sudah ada
$serviceId = $null
foreach ($s in $services) {
    Write-Host "  -> Service: $($s.node.name) (ID: $($s.node.id))" -ForegroundColor Yellow
    $serviceId = $s.node.id
}

if (-not $serviceId) {
    Write-Host "`n[2/6] Membuat service baru dari GitHub repo..." -ForegroundColor Cyan
    $createServiceQuery = @"
mutation {
  serviceCreate(input: {
    projectId: "$PROJECT_ID"
    source: { repo: "UltimateSky/Saphire-Discord-bot" }
  }) {
    id
    name
  }
}
"@
    $serviceData = Invoke-RailwayAPI $createServiceQuery
    $serviceId = $serviceData.data.serviceCreate.id
    Write-Host "  Service dibuat: $serviceId" -ForegroundColor Green
} else {
    Write-Host "`n[2/6] Service sudah ada, skip pembuatan." -ForegroundColor Green
}

# Dapatkan environment ID (production)
Write-Host "`n[3/6] Mengambil environment ID..." -ForegroundColor Cyan
$envQuery = @"
query {
  project(id: "$PROJECT_ID") {
    environments { edges { node { id name } } }
  }
}
"@
$envData = Invoke-RailwayAPI $envQuery
$envId = $null
foreach ($e in $envData.data.project.environments.edges) {
    if ($e.node.name -eq "production") {
        $envId = $e.node.id
    }
}
Write-Host "  Environment ID: $envId" -ForegroundColor Green

# Set environment variables
Write-Host "`n[4/6] Menambahkan environment variables..." -ForegroundColor Cyan
$envVars = @{
    "DISCORD_TOKEN" = (Get-Content .env | Select-String "DISCORD_TOKEN=").ToString().Split("=")[1].Trim()
    "GUILD_ID" = "1314664583478382602"
    "SPOTIFY_CLIENT_ID" = "ad9d996bc09145ceafa27b6079c0c87f"
    "SPOTIFY_CLIENT_SECRET" = "9e76f81b022f48489ef993ed8758dbcc"
    "GENIUS_API_TOKEN" = "QPJGk-RXVU3hRAXFWtmq5PjCYrfK_3v5-lcTPzWVFN83aT69c1Ac_iCXeyH2cN99"
}

foreach ($key in $envVars.Keys) {
    $val = $envVars[$key]
    $setVarQuery = @"
mutation {
  variableUpsert(input: {
    projectId: "$PROJECT_ID"
    serviceId: "$serviceId"
    environmentId: "$envId"
    name: "$key"
    value: "$val"
  })
}
"@
    Invoke-RailwayAPI $setVarQuery | Out-Null
    Write-Host "  + $key = ****" -ForegroundColor Green
}

# Tambah PostgreSQL plugin
Write-Host "`n[5/6] Menambahkan PostgreSQL database..." -ForegroundColor Cyan
Write-Host "  (Catatan: Jika sudah ada, akan di-skip)" -ForegroundColor Yellow

# Check existing plugins/databases  
$pluginQuery = @"
mutation {
  serviceCreate(input: {
    projectId: "$PROJECT_ID"
    source: { image: "ghcr.io/railwayapp-templates/postgres-ssl:latest" }
    name: "Postgres"
  }) {
    id
    name
  }
}
"@

try {
    $pluginData = Invoke-RailwayAPI $pluginQuery
    $pgServiceId = $pluginData.data.serviceCreate.id
    Write-Host "  PostgreSQL service dibuat: $pgServiceId" -ForegroundColor Green
    
    # Set DATABASE_URL reference variable  
    $dbUrlQuery = @"
mutation {
  variableUpsert(input: {
    projectId: "$PROJECT_ID"
    serviceId: "$serviceId"
    environmentId: "$envId"
    name: "DATABASE_URL"
    value: "`${{Postgres.DATABASE_URL}}"
  })
}
"@
    Invoke-RailwayAPI $dbUrlQuery | Out-Null
    Write-Host "  + DATABASE_URL = (linked to Postgres)" -ForegroundColor Green
} catch {
    Write-Host "  PostgreSQL mungkin sudah ada, mencoba link saja..." -ForegroundColor Yellow
}

# Generate domain  
Write-Host "`n[6/6] Generating public domain..." -ForegroundColor Cyan
$domainQuery = @"
mutation {
  serviceDomainCreate(input: {
    serviceId: "$serviceId"
    environmentId: "$envId"
  }) {
    id
    domain
  }
}
"@
try {
    $domainData = Invoke-RailwayAPI $domainQuery
    $domain = $domainData.data.serviceDomainCreate.domain
    Write-Host "  Domain: https://$domain" -ForegroundColor Green
} catch {
    Write-Host "  Domain mungkin sudah ada." -ForegroundColor Yellow
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  SETUP SELESAI!" -ForegroundColor Green
Write-Host "  Bot sedang di-deploy di Railway." -ForegroundColor Green
Write-Host "  Buka https://railway.com/project/$PROJECT_ID" -ForegroundColor Green
Write-Host "  untuk melihat status deployment." -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "Langkah terakhir:" -ForegroundColor Yellow
Write-Host "1. Buka https://ferry-sapphirebot.vercel.app" -ForegroundColor White
Write-Host "2. Klik 'Preview Mode' di pojok kiri atas" -ForegroundColor White
Write-Host "3. Masukkan URL: https://$domain" -ForegroundColor White
Write-Host "4. Klik OK - selesai!" -ForegroundColor White
