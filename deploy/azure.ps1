param(
    [Parameter(Mandatory = $true)] [string]$Name,
    [string]$Location = "polandcentral",
    [string]$ResourceGroup = "$Name-rg",
    [switch]$CodeOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Invoke-Az {
    & az @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') zakończyło się błędem" }
}

function New-Secret([int]$Length) {
    $sets = "ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnopqrstuvwxyz", "23456789"
    $all = -join $sets
    $chars = @($sets | ForEach-Object { $_[(Get-Random -Maximum $_.Length)] })
    $chars += 1..($Length - $chars.Count) | ForEach-Object { $all[(Get-Random -Maximum $all.Length)] }
    -join ($chars | Sort-Object { Get-Random })
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Brak Azure CLI. Zainstaluj: winget install Microsoft.AzureCLI, potem az login."
}
& az account show --output none 2>$null
if ($LASTEXITCODE -ne 0) { throw "Zaloguj się: az login" }

if (-not $CodeOnly) {
    $db = "$Name-db"
    $dbUser = "geoadmin"
    $dbPassword = New-Secret 24
    $adminPassword = New-Secret 16

    Write-Host "Grupa zasobów $ResourceGroup ($Location)"
    Invoke-Az group create --name $ResourceGroup --location $Location --output none

    Write-Host "PostgreSQL $db (kilka minut)"
    Invoke-Az postgres flexible-server create --resource-group $ResourceGroup --name $db --location $Location `
        --tier Burstable --sku-name Standard_B1ms --storage-size 32 --version 16 `
        --admin-user $dbUser --admin-password $dbPassword --database-name cultureguessr `
        --public-access 0.0.0.0 --yes --output none
    Invoke-Az postgres flexible-server parameter set --resource-group $ResourceGroup --server-name $db `
        --name azure.extensions --value POSTGIS --output none

    Write-Host "App Service $Name"
    Invoke-Az appservice plan create --resource-group $ResourceGroup --name "$Name-plan" --location $Location `
        --is-linux --sku B1 --output none
    Invoke-Az webapp create --resource-group $ResourceGroup --plan "$Name-plan" --name $Name `
        --runtime "PYTHON:3.11" --output none
    Invoke-Az webapp config appsettings set --resource-group $ResourceGroup --name $Name --output none --settings `
        "SCM_DO_BUILD_DURING_DEPLOYMENT=true" `
        "DATABASE_URL=postgresql://${dbUser}:${dbPassword}@$db.postgres.database.azure.com:5432/cultureguessr" `
        "SECRET_KEY=$(New-Secret 48)" `
        "ADMIN_PASSWORD=$adminPassword" `
        "SEED_ON_START=1"
    Invoke-Az webapp config set --resource-group $ResourceGroup --name $Name `
        --startup-file "sh startup.sh" --always-on true --output none
}

Write-Host "Wdrażam ostatni commit (HEAD)"
$zip = Join-Path $env:TEMP "cultureguessr-deploy.zip"
git -C $root archive --format zip --output $zip HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive nie powiodło się" }
Invoke-Az webapp deploy --resource-group $ResourceGroup --name $Name --src-path $zip --type zip --output none
Remove-Item $zip

Write-Host ""
Write-Host "Gotowe: https://$Name.azurewebsites.net"
if (-not $CodeOnly) {
    Write-Host "Hasło do /admin: $adminPassword (zapisz je, nie jest nigdzie zapisywane)"
}
