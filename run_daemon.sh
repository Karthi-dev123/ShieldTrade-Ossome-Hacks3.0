#!/bin/bash
export GEMINI_API_KEY=$(grep "^GEMINI_API_KEY=" env.txt | head -n 1 | cut -d '=' -f 2)
export GOOGLE_API_KEY=$GEMINI_API_KEY
nohup /home/naithick/.nvm/versions/node/v22.16.0/bin/openclaw gateway run --force </dev/null >/tmp/daemon.log 2>&1 &
disown
