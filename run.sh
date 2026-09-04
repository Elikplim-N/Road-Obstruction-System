#!/usr/bin/env bash
# Directly starts the Minimalist Enterprise IoT Fleet Management Platform
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$PROJECT_DIR/desktop_app:$PYTHONPATH"

PORT=9000
echo "======================================================================"
echo " 🌐 STARTING HIGHWAY ROAD OBSTRUCTION IoT FLEET MANAGEMENT PLATFORM"
echo "======================================================================"
echo " Access URL: http://localhost:$PORT"
echo " Network URL: http://$(hostname -I | awk '{print $1}'):$PORT"
echo "======================================================================"

python3 "$PROJECT_DIR/iot_management_app/backend/server.py" $PORT
