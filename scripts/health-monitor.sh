#!/bin/bash
# Personal Layer Health Monitor
# Run this periodically to check the local Python runtime health.

LOG_FILE="$HOME/.personalayer/logs/health.log"
mkdir -p "$(dirname "$LOG_FILE")"

DAEMON_PORT=7823

check_daemon() {
    if lsof -Pi :"$DAEMON_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "$(date): daemon OK (port $DAEMON_PORT)"
        return 0
    else
        echo "$(date): daemon DOWN (port $DAEMON_PORT)"
        return 1
    fi
}

# Main
check_daemon >> "$LOG_FILE" 2>&1
