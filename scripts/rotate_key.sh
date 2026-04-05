#!/bin/bash
# Legacy helper kept for compatibility with older scripts.
# Returns the active local model name instead of rotating cloud keys.
echo -n "${OLLAMA_MODEL:-llama3.2:3b}"
