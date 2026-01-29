#!/usr/bin/env bash
# =============================================================================
# SIP Relay Server v2 - Docker Build Script
# =============================================================================
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
IMAGE_NAME="sip-server-v2"
IMAGE_TAG="latest"
COMPOSE_FILE="docker-compose.yml"

# Functions
print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  SIP Relay Server v2 - Docker Build${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

usage() {
    cat << EOF
Usage: $(basename "$0") [COMMAND] [OPTIONS]

Commands:
    build       Build Docker images
    up          Build and start services
    down        Stop and remove containers
    restart     Restart services
    logs        View service logs
    status      Show container status
    clean       Remove images and volumes
    shell       Open shell in container
    help        Show this help message

Options:
    -t, --tag TAG       Image tag (default: latest)
    -f, --file FILE     Compose file (default: docker-compose.yml)
    --no-cache          Build without cache
    --gpu               Enable GPU support

Examples:
    $(basename "$0") build
    $(basename "$0") up
    $(basename "$0") logs -f
    $(basename "$0") shell sip-server
    $(basename "$0") build --no-cache --tag v1.0.0

EOF
}

check_requirements() {
    print_info "Checking requirements..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    print_success "Docker found: $(docker --version)"

    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose v2 is not installed"
        exit 1
    fi
    print_success "Docker Compose found: $(docker compose version --short)"

    # Check .env file
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        print_warning ".env file not found"
        if [[ -f "$PROJECT_ROOT/.env.docker.example" ]]; then
            print_info "Creating .env from .env.docker.example..."
            cp "$PROJECT_ROOT/.env.docker.example" "$PROJECT_ROOT/.env"
            print_warning "Please edit .env with your configuration"
        fi
    else
        print_success ".env file found"
    fi

    # Check voices directory
    if [[ ! -d "$PROJECT_ROOT/voices" ]]; then
        print_warning "voices/ directory not found - TTS may not work"
    else
        voice_count=$(find "$PROJECT_ROOT/voices" -name "*.onnx" 2>/dev/null | wc -l)
        print_success "voices/ directory found ($voice_count voice models)"
    fi

    # Check greeting audio
    if [[ ! -f "$PROJECT_ROOT/output/transcode/greeting.wav" ]]; then
        print_warning "output/transcode/greeting.wav not found"
        mkdir -p "$PROJECT_ROOT/output/transcode"
    else
        print_success "Greeting audio found"
    fi

    echo
}

do_build() {
    local no_cache=""

    if [[ "${NO_CACHE:-}" == "true" ]]; then
        no_cache="--no-cache"
    fi

    print_info "Building Docker images..."
    cd "$PROJECT_ROOT"

    docker compose -f "$COMPOSE_FILE" build $no_cache

    print_success "Build complete"
    echo
    docker images | grep "$IMAGE_NAME" || true
}

do_up() {
    print_info "Starting services..."
    cd "$PROJECT_ROOT"

    docker compose -f "$COMPOSE_FILE" up -d --build

    print_success "Services started"
    echo
    docker compose -f "$COMPOSE_FILE" ps
}

do_down() {
    print_info "Stopping services..."
    cd "$PROJECT_ROOT"

    docker compose -f "$COMPOSE_FILE" down

    print_success "Services stopped"
}

do_restart() {
    print_info "Restarting services..."
    cd "$PROJECT_ROOT"

    docker compose -f "$COMPOSE_FILE" restart

    print_success "Services restarted"
    echo
    docker compose -f "$COMPOSE_FILE" ps
}

do_logs() {
    cd "$PROJECT_ROOT"

    # Pass remaining args to logs command
    docker compose -f "$COMPOSE_FILE" logs "${@}"
}

do_status() {
    cd "$PROJECT_ROOT"

    echo -e "${BLUE}Container Status:${NC}"
    docker compose -f "$COMPOSE_FILE" ps

    echo
    echo -e "${BLUE}Resource Usage:${NC}"
    docker stats --no-stream $(docker compose -f "$COMPOSE_FILE" ps -q) 2>/dev/null || true
}

do_clean() {
    print_warning "This will remove all containers, images, and volumes"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Stopping containers..."
        cd "$PROJECT_ROOT"
        docker compose -f "$COMPOSE_FILE" down -v --rmi local

        print_info "Removing dangling images..."
        docker image prune -f

        print_success "Cleanup complete"
    else
        print_info "Cancelled"
    fi
}

do_shell() {
    local container="${1:-sip-server}"

    print_info "Opening shell in $container..."
    cd "$PROJECT_ROOT"

    docker compose -f "$COMPOSE_FILE" exec "$container" /bin/bash
}

enable_gpu() {
    print_info "Enabling GPU support..."

    # Check for NVIDIA runtime
    if ! docker info 2>/dev/null | grep -q "nvidia"; then
        print_warning "NVIDIA runtime not detected"
        print_info "Install nvidia-container-toolkit for GPU support"
    else
        print_success "NVIDIA runtime detected"
    fi

    # GPU configuration is handled in docker-compose.yml
    export COMPOSE_PROFILES="gpu"
}

# =============================================================================
# Main
# =============================================================================

cd "$PROJECT_ROOT"

# Parse arguments
COMMAND="${1:-help}"
shift || true

NO_CACHE="false"
GPU_ENABLED="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -f|--file)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE="true"
            shift
            ;;
        --gpu)
            GPU_ENABLED="true"
            shift
            ;;
        *)
            break
            ;;
    esac
done

# Execute command
case "$COMMAND" in
    build)
        print_header
        check_requirements
        [[ "$GPU_ENABLED" == "true" ]] && enable_gpu
        do_build
        ;;
    up)
        print_header
        check_requirements
        [[ "$GPU_ENABLED" == "true" ]] && enable_gpu
        do_up
        ;;
    down)
        do_down
        ;;
    restart)
        do_restart
        ;;
    logs)
        do_logs "${@}"
        ;;
    status)
        do_status
        ;;
    clean)
        do_clean
        ;;
    shell)
        do_shell "${1:-sip-server}"
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        echo
        usage
        exit 1
        ;;
esac
