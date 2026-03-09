#!/bin/bash
# OTA Push - Watch for file changes and auto-upload to ESP32-S3 over WiFi
# Usage: ./ota_push.sh [device_ip]
# Example: ./ota_push.sh 192.168.71.154

DEVICE_IP="${1:-192.168.71.157}"
DEVICE_URL="http://${DEVICE_IP}"
WATCH_FILES="config.py settings.py stepper.py ssd1306.py wifi_manager.py webserver.py main.py"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

upload_file() {
    local file="$1"
    local tmpfile
    tmpfile=$(mktemp)
    # Use python to safely JSON-encode file content to a temp file
    python3 -c "
import json, sys
with open(sys.argv[1], 'r') as f:
    content = f.read()
with open(sys.argv[2], 'w') as out:
    json.dump({'filename': sys.argv[1], 'content': content}, out)
" "$file" "$tmpfile"

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d @"$tmpfile" \
        "${DEVICE_URL}/api/ota/upload" 2>&1)
    rm -f "$tmpfile"

    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | head -n -1)

    if [ "$http_code" = "200" ]; then
        local bytes
        bytes=$(echo "$body" | python3 -c "import json,sys; print(json.load(sys.stdin).get('bytes','?'))" 2>/dev/null)
        echo -e "  ${GREEN}OK${NC} (${bytes} bytes)"
        return 0
    else
        echo -e "  ${RED}FAILED${NC} (HTTP ${http_code}): ${body}"
        return 1
    fi
}

# Check for inotifywait
if ! command -v inotifywait &>/dev/null; then
    echo -e "${RED}Error: inotifywait not found${NC}"
    echo "Install with: sudo apt install inotify-tools"
    exit 1
fi

# Check device is reachable
echo -e "${CYAN}Checking device at ${DEVICE_URL}...${NC}"
if ! curl -s --connect-timeout 3 "${DEVICE_URL}/api/ota/files" >/dev/null 2>&1; then
    echo -e "${RED}Cannot reach device at ${DEVICE_IP}${NC}"
    echo "Make sure the ESP32 is running and on the same network."
    exit 1
fi
echo -e "${GREEN}Device online${NC}"
echo ""

# Option: upload all files first
read -p "Upload all files now? (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}Uploading all files...${NC}"
    fail=0
    for file in $WATCH_FILES; do
        if [ -f "$file" ]; then
            echo -n "  $file..."
            upload_file "$file" || fail=1
        fi
    done
    if [ $fail -eq 0 ]; then
        echo -e "${GREEN}All files uploaded${NC}"
        read -p "Reboot device? (y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            curl -s -X POST -H "Content-Type: application/json" -d '{}' "${DEVICE_URL}/api/ota/reboot" >/dev/null 2>&1
            echo -e "${YELLOW}Rebooting...${NC}"
            sleep 8
        fi
    fi
    echo ""
fi

echo -e "${CYAN}Watching for changes...${NC} (Ctrl+C to stop)"
echo -e "Files: ${WATCH_FILES}"
echo ""

# Watch for file changes and auto-upload
while true; do
    changed=$(inotifywait -q -e close_write --format '%f' $WATCH_FILES 2>/dev/null)
    if [ -n "$changed" ] && [ -f "$changed" ]; then
        echo -ne "${YELLOW}$(date +%H:%M:%S)${NC} ${changed} changed, uploading..."
        if upload_file "$changed"; then
            echo -ne "  ${CYAN}Reboot? (y/N, 3s timeout) ${NC}"
            read -t 3 -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                curl -s -X POST -H "Content-Type: application/json" -d '{}' "${DEVICE_URL}/api/ota/reboot" >/dev/null 2>&1
                echo -e "  ${YELLOW}Rebooting...${NC}"
                sleep 8
                echo -e "  ${GREEN}Ready${NC}"
            fi
        fi
    fi
done
