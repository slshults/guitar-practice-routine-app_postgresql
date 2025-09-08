#!/bin/bash

# Set up colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Store PIDs for cleanup
declare -a PIDS=()

# Function to cleanup processes on exit
cleanup() {
    echo -e "\n${BLUE}Cleaning up processes...${NC}"
    
    # Kill all stored PIDs and their children
    for pid in "${PIDS[@]}"; do
        if kill -0 $pid 2>/dev/null; then
            echo -e "${BLUE}Stopping process $pid and children...${NC}"
            pkill -P $pid 2>/dev/null
            kill -TERM $pid 2>/dev/null
            sleep 1
            pkill -P $pid 2>/dev/null
            kill -KILL $pid 2>/dev/null
        fi
    done
    
    # Additional cleanup for any remaining processes
    for cmd in "flask run" "npm run watch" "inotifywait" "python.*run.py"; do
        pids=$(pgrep -f "$cmd" 2>/dev/null)
        if [ -n "$pids" ]; then
            echo -e "${BLUE}Stopping $cmd processes...${NC}"
            pkill -TERM -f "$cmd" 2>/dev/null
            sleep 1
            pkill -KILL -f "$cmd" 2>/dev/null
        fi
    done
    
    echo -e "${GREEN}Cleanup complete${NC}"
    exit 0
}

# Error handling function
handle_error() {
    echo -e "${RED}Error: $1${NC}"
    cleanup
}

# Function to check if a process is running
is_process_running() {
    local pid=$1
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to start a process and store its PID
start_process() {
    "$@" &
    local pid=$!
    PIDS+=($pid)
    return $pid
}

# Trap cleanup function for script termination
trap cleanup SIGINT SIGTERM EXIT

# Load nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Use Node.js 18
echo -e "${BLUE}Setting up Node.js environment...${NC}"
nvm use 18 || handle_error "Failed to set Node.js version"

# Initial build
echo -e "${GREEN}Building assets...${NC}"
npm run build || handle_error "Failed to build assets"

# Start Flask with auto-reloader (but in prod mode)
echo -e "${GREEN}Starting Flask server...${NC}"
FLASK_ENV=production FLASK_DEBUG=1 FLASK_APP=run.py flask run --host=0.0.0.0 --port=5000 &
FLASK_PID=$!
PIDS+=($FLASK_PID)

# Wait a moment to ensure Flask starts
sleep 2

# Check if Flask started successfully
if ! is_process_running $FLASK_PID; then
    handle_error "Flask server failed to start"
fi

# Start Vite with hot module replacement
echo -e "${GREEN}Starting Vite...${NC}"
npm run watch &
VITE_PID=$!
PIDS+=($VITE_PID)

# Wait a moment to ensure Vite starts
sleep 2

# Check if Vite started successfully
if ! is_process_running $VITE_PID; then
    handle_error "Vite watch failed to start"
fi

# Start file watcher for Python files with debouncing
echo -e "${GREEN}Starting Python file watcher...${NC}"
(
    while inotifywait -r -e modify --include='.*\.py$' ./app; do
        echo -e "${YELLOW}Python files changed, waiting for more changes...${NC}"
        # Debounce: wait 3 seconds for additional changes before restarting
        sleep 3
        
        # Check if more changes occurred during the wait
        if inotifywait -r -e modify --include='.*\.py$' --timeout 1 ./app 2>/dev/null; then
            echo -e "${YELLOW}More changes detected, extending wait...${NC}"
            sleep 2
        fi
        
        echo -e "${YELLOW}Restarting Flask server...${NC}"
        if is_process_running $FLASK_PID; then
            kill $FLASK_PID
            wait $FLASK_PID 2>/dev/null
        fi
        FLASK_ENV=production FLASK_DEBUG=1 FLASK_APP=run.py flask run --host=0.0.0.0 --port=5000 &
        FLASK_PID=$!
        PIDS+=($FLASK_PID)
        sleep 2
        if ! is_process_running $FLASK_PID; then
            echo -e "${RED}Failed to restart Flask server${NC}"
        else
            echo -e "${GREEN}Flask server restarted successfully${NC}"
        fi
    done
) &
WATCHER_PID=$!
PIDS+=($WATCHER_PID)

echo -e "${GREEN}Guitar Practice Routine App is ready!${NC}"
echo -e "${BLUE}Press Ctrl+C to stop all processes${NC}"

# Wait for all background processes
wait