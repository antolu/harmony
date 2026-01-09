#!/bin/bash
set -e

echo "=== Harmony Elasticsearch Integration Tests ==="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cleanup() {
    echo -e "${YELLOW}Stopping services...${NC}"
    docker compose -f docker-compose.test.yml down -v
}

trap cleanup EXIT

# Start Elasticsearch
echo -e "${GREEN}Starting Elasticsearch...${NC}"
docker compose -f docker-compose.test.yml up -d

# Wait for Elasticsearch to be healthy
echo -e "${YELLOW}Waiting for Elasticsearch to be ready...${NC}"
for i in {1..30}; do
    if docker compose -f docker-compose.test.yml ps elasticsearch | grep -q "healthy"; then
        echo ""
        break
    fi
    echo -n "."
    sleep 2
    if [ $i -eq 30 ]; then
        echo ""
        echo -e "${RED}Elasticsearch failed to start${NC}"
        exit 1
    fi
done

# Verify connection
echo -e "${GREEN}Verifying Elasticsearch connection...${NC}"
curl -f http://localhost:9200/_cluster/health || {
    echo -e "${RED}Failed to connect to Elasticsearch${NC}"
    exit 1
}
echo ""

# Run tests
echo -e "${GREEN}Running Elasticsearch integration tests...${NC}"
pytest tests/ -v --tb=short -m "elasticsearch and not llm" "$@"

echo -e "${GREEN}Tests completed successfully!${NC}"
