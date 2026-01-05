#!/bin/bash
# Egyptian AI Medication Validation Engine
# Quick Start Script

set -e

echo "=============================================="
echo "Egyptian AI Medication Validation Engine"
echo "HealthFlow Group - Quick Start"
echo "=============================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo "Docker is required but not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "docker-compose is required but not installed. Please install docker-compose first."
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites satisfied${NC}"

# Create data directory
echo -e "${YELLOW}Setting up directories...${NC}"
mkdir -p data models

# Copy drug database if provided
if [ -f "cfgdrug.xlsx" ]; then
    cp cfgdrug.xlsx data/
    echo -e "${GREEN}✓ Drug database copied to data/${NC}"
else
    echo -e "${YELLOW}⚠ cfgdrug.xlsx not found in current directory${NC}"
    echo "  Please copy your Egyptian drug database to data/cfgdrug.xlsx"
fi

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d postgres redis

echo "Waiting for databases to be ready..."
sleep 10

# Start API
docker-compose up -d medication-api

echo "Waiting for API to start..."
sleep 5

# Check health
echo -e "${YELLOW}Checking service health...${NC}"
HEALTH=$(curl -s http://localhost:8000/health || echo '{"status":"error"}')
echo "Health check response: $HEALTH"

# Load database if file exists
if [ -f "data/cfgdrug.xlsx" ]; then
    echo -e "${YELLOW}Loading Egyptian drug database...${NC}"
    LOAD_RESULT=$(curl -s -X POST "http://localhost:8000/admin/load-database?filepath=/data/cfgdrug.xlsx")
    echo "Load result: $LOAD_RESULT"
fi

echo ""
echo -e "${GREEN}=============================================="
echo "Setup Complete!"
echo "=============================================="
echo ""
echo "API Endpoints:"
echo "  - Swagger Docs: http://localhost:8000/docs"
echo "  - Health Check: http://localhost:8000/health"
echo "  - Statistics:   http://localhost:8000/statistics"
echo ""
echo "Quick Test:"
echo '  curl -X POST "http://localhost:8000/validate/quick" \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '\''{"medication_ids": [103473, 103474]}'\'''
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""
echo -e "${NC}"
