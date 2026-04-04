#!/bin/bash
export $(grep "^GEMINI_API_KEY=" env.txt)
export GOOGLE_API_KEY=$GEMINI_API_KEY
export GOOGLE_GENAI_API_KEY=$GEMINI_API_KEY
nohup /home/naithick/.nvm/versions/node/v22.16.0/bin/openclaw gateway run --force > gateway.log 2>&1 &
