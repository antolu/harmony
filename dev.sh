#!/bin/bash

# Development environment management script for Harmony Admin

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[DEV]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi

    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not available"
        exit 1
    fi
}

start_dev() {
    print_status "Starting development environment..."
    print_status "This will:"
    print_status "  - Mount source code for live reload"
    print_status "  - Frontend (Vite) with HMR on port 3001"
    print_status "  - Backend (Uvicorn) with auto-reload on port 8000"
    print_status ""

    # Stop existing containers
    docker compose -f docker-compose.dev.yml down 2>/dev/null || true

    # Build development images
    print_status "Building development images..."
    DOCKER_BUILDKIT=1 docker compose -f docker-compose.dev.yml build

    # Start development environment
    print_status "Starting containers..."
    docker compose -f docker-compose.dev.yml up -d

    print_status "Development environment started!"
    print_status ""
    print_status "Access URLs:"
    print_status "  Frontend: http://localhost:3001"
    print_status "  Backend API: http://localhost:8000"
    print_status "  Elasticsearch: http://localhost:9200"
    print_status ""
    print_status "Commands:"
    print_status "  View logs: ./dev.sh logs [service] [-f]"
    print_status "  Stop: ./dev.sh stop"
    print_status "  Restart: ./dev.sh restart"
}

stop_dev() {
    print_status "Stopping development environment..."
    docker compose -f docker-compose.dev.yml down
    print_status "Development environment stopped!"
}

restart_dev() {
    print_status "Restarting development environment..."
    stop_dev
    start_dev
}

show_logs() {
    service=""
    follow_flag=""

    # Parse arguments
    shift # skip the 'logs' command
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f)
                follow_flag="-f"
                shift
                ;;
            *)
                service="$1"
                shift
                ;;
        esac
    done

    if [ -n "$service" ]; then
        docker compose -f docker-compose.dev.yml logs $follow_flag "$service"
    else
        docker compose -f docker-compose.dev.yml logs $follow_flag
    fi
}

rebuild() {
    print_status "Rebuilding development images..."
    docker compose -f docker-compose.dev.yml build --no-cache
    print_status "Rebuild complete!"
}

shell() {
    service="${2:-harmony-admin-backend}"
    print_status "Opening shell in $service..."
    docker compose -f docker-compose.dev.yml exec "$service" sh
}

show_help() {
    echo "Harmony Admin Development Environment"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start              Start development environment with live reload"
    echo "  stop               Stop development environment"
    echo "  restart            Restart development environment"
    echo "  logs [service] [-f] Show logs (optional service name, -f to follow)"
    echo "  rebuild            Rebuild development images"
    echo "  shell [service]    Open shell in container (default: backend)"
    echo "  help               Show this help message"
    echo ""
    echo "Services:"
    echo "  harmony-admin-frontend   Vite dev server (port 3001)"
    echo "  harmony-admin-backend    FastAPI backend (port 8001)"
    echo "  elasticsearch            Elasticsearch (port 9200)"
    echo ""
    echo "Development URLs:"
    echo "  Frontend: http://localhost:3001"
    echo "  Backend:  http://localhost:8001"
    echo "  API Docs: http://localhost:8001/docs"
}

# Main
check_dependencies

case "${1:-help}" in
    "start"|"dev")
        start_dev
        ;;
    "stop")
        stop_dev
        ;;
    "restart")
        restart_dev
        ;;
    "logs")
        show_logs "$@"
        ;;
    "rebuild")
        rebuild
        ;;
    "shell")
        shell "$@"
        ;;
    "help"|*)
        show_help
        ;;
esac
