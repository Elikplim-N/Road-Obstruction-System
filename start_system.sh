#!/usr/bin/env bash
# ==============================================================================
# Smart Highway Road Obstruction Detection & LoRa Alert System Launcher
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$PROJECT_DIR/desktop_app:$PYTHONPATH"

echo "======================================================================"
echo " 🚗 SMART HIGHWAY ROAD OBSTRUCTION & IOT FLEET PLATFORM"
echo "======================================================================"
echo " 1) Launch Minimalist White IoT Fleet Management Platform (Port 9000)"
echo " 2) Launch Desktop Native GUI App (PyQt6 / PyQt5 Hub)"
echo " 3) Run System Performance Evaluation Benchmark (Objective 7 Report)"
echo " 4) Launch Desktop Native App on Live Camera Feed immediately (--live)"
echo " 5) Open Incident Storage & Evidence Directory"
echo " 6) Exit"
echo "======================================================================"
read -p "Select an option [1-6]: " choice

case $choice in
    1)
        echo "Starting Minimalist White IoT Management Platform on http://localhost:9000..."
        python3 "$PROJECT_DIR/iot_management_app/backend/server.py" 9000
        ;;
    2)
        echo "Launching Desktop Native GUI Application..."
        python3 "$PROJECT_DIR/desktop_app/main.py"
        ;;
    3)
        echo "Running Performance Evaluation Suite..."
        python3 "$PROJECT_DIR/desktop_app/evaluate_system.py"
        ;;
    4)
        echo "Launching Desktop Native App on Live Camera Feed..."
        python3 "$PROJECT_DIR/desktop_app/main.py" --live
        ;;
    5)
        echo "Opening Storage Directory: $PROJECT_DIR/desktop_app/sample_data"
        xdg-open "$PROJECT_DIR/desktop_app/sample_data" 2>/dev/null || ls -la "$PROJECT_DIR/desktop_app/sample_data"
        ;;
    *)
        echo "Exiting."
        exit 0
        ;;
esac
