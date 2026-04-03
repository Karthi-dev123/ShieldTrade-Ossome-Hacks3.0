#!/bin/bash
echo "Starting ShieldTrade E2E Evaluation..."

if [ ! -f ".env" ]; then
    echo "Error: .env file missing! Please put the .env file provided personally in this root folder."
    exit 1
fi

if grep -q "USE_OLLAMA=true" .env; then
    echo "Local AI Fallback detected (USE_OLLAMA=true)."
    if ! command -v ollama &> /dev/null; then
        echo "Ollama is not installed. Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
    else
        echo "Ollama is already installed."
    fi
fi

python scripts/start-all.py
