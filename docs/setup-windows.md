# ShieldTrade — Windows Setup Guide (PowerShell)

> **IMPORTANT**: All commands below must be run in **PowerShell**, preferably as Administrator for the initial tool installations.

## 1. Prerequisites & Node Version Management

ShieldTrade strictly requires Node.js 22.16.0. We use `nvm-windows` to manage this.

```powershell
# 1. Install nvm-windows (if not already installed)
winget install coreybutler.nvm.windows

# 2. Restart your PowerShell terminal so 'nvm' is recognized

# 3. Install and use the required Node.js version
nvm install 22.16.0
nvm use 22.16.0

# 4. Verify version (must output v22.16.0)
node -v
```

## 2. Directory Structure Scaffolding

Create the required workspace structure using PowerShell commands:

```powershell
# Create root directory and navigate into it
New-Item -ItemType Directory -Force -Path "shieldtrade"
Set-Location "shieldtrade"

# Create folder structure
$folders = @(
    "config",
    "scripts",
    "skills\shieldtrade-analyst",
    "skills\shieldtrade-risk-manager",
    "skills\shieldtrade-trader",
    "output\reports",
    "output\risk-decisions",
    "output\trade-logs",
    "output\thoughts",
    "data\market",
    "data\earnings",
    "tests",
    "docs"
)

foreach ($folder in $folders) {
    New-Item -ItemType Directory -Force -Path $folder
}

# Create base files
$files = @(
    "config\openclaw.json",
    "config\shieldtrade-policies.yaml",
    "scripts\alpaca_bridge.py",
    "scripts\policy_engine.py",
    "scripts\proxy.js",
    "tests\test_policy_engine.py"
)

foreach ($file in $files) {
    New-Item -ItemType File -Force -Path $file
}
```

## 3. Environment Variables

Create the `.env.example` file:

```powershell
$envContent = @"
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ARMORIQ_API_KEY=
GEMINI_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
"@

Set-Content -Path ".env.example" -Value $envContent
Copy-Item ".env.example" -Destination ".env"
```
*(Remember to fill in your `.env` values before running the system)*

## 4. Install Global Dependencies & ArmorClaw

```powershell
# Install OpenClaw and pnpm globally
npm install -g openclaw@2026.3.28
npm install -g pnpm@10.6.5

# Install ArmorClaw (Windows alternative to the curl|bash script)
Invoke-WebRequest -Uri "https://armoriq.ai/install-armorclaw.ps1" -OutFile "install-armorclaw.ps1"
.\install-armorclaw.ps1
Remove-Item "install-armorclaw.ps1"
```

## 5. Python Setup

You must have Python 3.12.3 installed.

```powershell
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies (make sure your terminal shows (venv) prefix)
pip install alpaca-py supabase PyYAML==6.0.2 filelock==3.16.1 pytest==8.3.5 httpx==0.28.1 python-dotenv==1.1.0
```

## 6. Running the System

To bypass API rate limits, you must run the local proxy and the OpenClaw gateway simultaneously. **You need two separate PowerShell windows.**

**Terminal Window 1 (The LLM Proxy):**
```powershell
Set-Location "path\to\shieldtrade"
# Make sure your .env has GEMINI_API_KEY set
node scripts\proxy.js
# This should output "Proxy running on port 4000"
```

**Terminal Window 2 (The OpenClaw Gateway):**
```powershell
Set-Location "path\to\shieldtrade"
# Activate the python environment so the policy engine is available
.\venv\Scripts\Activate.ps1

# Start the gateway
openclaw gateway start
```