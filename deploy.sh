#!/usr/bin/env bash
"""
deploy.sh - Automation utility for server lifecycle management and GitHub sync.
"""

# Exit immediately if a command exits with a non-zero status
set -o pipefail

# Project paths
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_SCRIPT="${PROJECT_DIR}/server.py"
PID_FILE="${PROJECT_DIR}/server.pid"
LOG_FILE="${PROJECT_DIR}/server.log"

# Default Host & Port config
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT=8080

function print_usage() {
    echo "Usage: $0 {start|stop|restart|status|logs|push}"
    echo "  start   : Starts the agent server in the background"
    echo "  stop    : Stops the running agent server"
    echo "  restart : Restarts the agent server"
    echo "  status  : Checks server running state"
    echo "  logs    : Tails server stdout/stderr logs"
    echo "  push    : Commits unstaged changes and pushes to GitHub"
}

function start_server() {
    if [ -f "${PID_FILE}" ]; then
        PID=$(cat "${PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            echo "Server is already running (PID: ${PID})."
            return 0
        else
            rm -f "${PID_FILE}"
        fi
    fi

    echo "Starting Agent Server on ${DEFAULT_HOST}:${DEFAULT_PORT}..."
    
    # Execute in background and redirect logs
    nohup python3 "${SERVER_SCRIPT}" --host "${DEFAULT_HOST}" --port "${DEFAULT_PORT}" > "${LOG_FILE}" 2>&1 &
    
    PID=$!
    echo "${PID}" > "${PID_FILE}"
    
    # Give the server a moment to bind to the port
    sleep 1
    
    if kill -0 "${PID}" 2>/dev/null; then
        echo "Server successfully started (PID: ${PID}). Logs: server.log"
    else
        echo "Error: Server failed to start. Check logs in server.log."
        exit 1
    fi
}

function stop_server() {
    if [ -f "${PID_FILE}" ]; then
        PID=$(cat "${PID_FILE}")
        echo "Stopping Agent Server (PID: ${PID})..."
        kill "${PID}" 2>/dev/null
        
        # Wait up to 5s for graceful exit
        for i in {1..5}; do
            if ! kill -0 "${PID}" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still alive
        if kill -0 "${PID}" 2>/dev/null; then
            echo "Server failed to stop gracefully. Force killing..."
            kill -9 "${PID}" 2>/dev/null
        fi
        
        rm -f "${PID_FILE}"
        echo "Server stopped."
    else
        echo "No running server found (server.pid missing)."
    fi
}

function check_status() {
    if [ -f "${PID_FILE}" ]; then
        PID=$(cat "${PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            echo "Server is RUNNING (PID: ${PID})."
            lsof -i :${DEFAULT_PORT} | grep "${PID}" || echo "Warning: Process running but not listening on port ${DEFAULT_PORT} yet."
        else
            echo "Server is STOPPED (Stale server.pid file found)."
        fi
    else
        echo "Server is STOPPED."
    fi
}

function tail_logs() {
    if [ -f "${LOG_FILE}" ]; then
        tail -n 50 -f "${LOG_FILE}"
    else
        echo "No logs found yet (server.log missing)."
    fi
}

function sync_github() {
    echo "Syncing changes to GitHub repository..."
    
    # Verify git status
    git status
    
    # Stage all changes
    git add -A
    
    # Read commit message
    echo -n "Enter commit message (default: 'updates through development phase'): "
    read -r MSG
    if [ -z "${MSG}" ]; then
        MSG="updates through development phase"
    fi
    
    git commit -m "${MSG}"
    
    echo "Pushing to remote main branch..."
    git push origin main
    
    if [ $? -eq 0 ]; then
        echo "Successfully pushed code changes to GitHub!"
    else
        echo "Error: Failed to push to GitHub. Check credentials or SSH/HTTPS keys."
        exit 1
    fi
}

# Handle subcommands
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        start_server
        ;;
    status)
        check_status
        ;;
    logs)
        tail_logs
        ;;
    push)
        sync_github
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
