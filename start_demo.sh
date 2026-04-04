#!/bin/bash
set -e

# Load environment using python
# Start proxy UI backend on port 5000
echo "Starting UI backend (Flask) on port 5000..."
source venv/bin/activate
export FLASK_APP=scripts/ui_backend.py
flask run -h 0.0.0.0 -p 5000 &
BACKEND_PID=$!

echo "Starting React UI..."
cd ui/shieldtrade
npm run dev -- --host &
UI_PID=$!

echo "--- RUNNING DEMO ---"
echo "Backend: http://localhost:5000"
echo "UI: http://localhost:5173"
echo "Press Ctrl+C to stop."

trap "kill $BACKEND_PID $UI_PID" EXIT
wait
