$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

function Passo($t) { Write-Host "`n== $t" -ForegroundColor Cyan }

# 1. Python
Passo "1/4 Verificando o Python"
$py = $null
foreach ($c in @("python", "py")) {
    try { & $c --version *> $null; if ($LASTEXITCODE -eq 0) { $py = $c; break } } catch {}
}
if (-not $py) {
    Write-Host "Python nao encontrado. Tentando instalar pelo winget..." -ForegroundColor Yellow
    try {
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        foreach ($c in @("python", "py")) { try { & $c --version *> $null; if ($LASTEXITCODE -eq 0) { $py = $c; break } } catch {} }
    } catch {}
}
if (-not $py) {
    Write-Host "Nao consegui instalar o Python sozinho. Instale em https://www.python.org/downloads/ (marque 'Add python.exe to PATH') e rode este instalador de novo." -ForegroundColor Red
    exit 1
}
Write-Host "Python ok ($py)"

# 2. Chaves do app no Bling
Passo "2/4 Chaves do Bling"
if (Test-Path ".env") {
    Write-Host "Arquivo .env ja existe, mantendo."
} else {
    Write-Host "Cole as chaves do seu app no Bling (Central de Extensoes > Area do Integrador)."
    Write-Host "O link de redirecionamento do app deve ser: http://localhost:8080/callback"
    $id = Read-Host "Client ID"
    $sec = Read-Host "Client Secret"
    if (-not $id -or -not $sec) { Write-Host "Chaves vazias. Cancelado." -ForegroundColor Red; exit 1 }
    "BLING_CLIENT_ID=$($id.Trim())`r`nBLING_CLIENT_SECRET=$($sec.Trim())`r`n" | Set-Content -Path ".env" -Encoding ascii
    Write-Host ".env criado."
}

# 3. Autorizacao
Passo "3/4 Autorizando no Bling"
if (Test-Path "tokens.json") {
    Write-Host "Ja autorizado nesta maquina."
} else {
    Write-Host "O navegador vai abrir. Faca login no Bling e clique em Autorizar."
    & $py bling.py auth
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path "tokens.json")) { Write-Host "A autorizacao falhou." -ForegroundColor Red; exit 1 }
}

# 4. Atalho na area de trabalho
Passo "4/4 Criando o atalho"
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "Precificador Bling.lnk"
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = Join-Path $dir "app\abrir.bat"
$s.WorkingDirectory = Join-Path $dir "app"
$s.WindowStyle = 7
$s.Description = "Precificador Bling - Loja Integrada Varejo"
$s.Save()
Write-Host "Atalho criado: $lnk" -ForegroundColor Green

Write-Host "`nPronto! Use o atalho 'Precificador Bling' na area de trabalho." -ForegroundColor Green
$ab = Read-Host "Abrir agora? (S/N)"
if ($ab -match '^[sS]') { Start-Process -FilePath (Join-Path $dir "app\abrir.bat") -WorkingDirectory (Join-Path $dir "app") }
