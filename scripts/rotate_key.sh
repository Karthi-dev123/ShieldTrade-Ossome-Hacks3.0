#!/bin/bash
# Simple random key rotation
KEYS=("$GEMINI_API_KEY1" "$GEMINI_API_KEY2" "$GEMINI_API_KEY3")
IDX=$((RANDOM % 3))
echo -n "${KEYS[$IDX]}"
