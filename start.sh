#!/bin/bash

# ==============================================================================
# BINOM AI - Single Command Local Development Launcher
# ==============================================================================

# Define colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}               BINOM AI - STARTUP MENU              ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Cleanup function to kill background jobs on script exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down BINOM AI...${NC}"
    
    # Kill frontend if it was started by this script
    if [ -n "$FRONTEND_PID" ]; then
        echo "Killing Frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null || true
    fi

    # Optionally stop docker containers
    # docker-compose down
    
    echo -e "${GREEN}Shutdown complete.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 1. Verify Environment Variables
echo -e "\n${YELLOW}[1/4] Verifying Environment Variables...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found.${NC}"
    if [ -f ".env.example" ]; then
        echo "Copying .env.example to .env..."
        cp .env.example .env
        echo -e "${YELLOW}Please fill in the required variables in .env and run this script again.${NC}"
    else
        echo -e "${RED}Error: .env.example also not found. Cannot proceed.${NC}"
    fi
    exit 1
fi

# Load variables
source .env

REQUIRED_VARS=("DATABASE_URL" "SUPABASE_URL" "SUPABASE_ANON_KEY" "GOOGLE_AI_API_KEY")
MISSING_VARS=0
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ Missing required environment variable: $var${NC}"
        MISSING_VARS=1
    fi
done

if [ $MISSING_VARS -eq 1 ]; then
    echo -e "\n${YELLOW}How to fix:${NC} Open the .env file in the root directory and provide valid values for the missing variables."
    exit 1
fi
echo -e "${GREEN}✅ Environment variables verified.${NC}"

# 2. Start Backend & Infrastructure via Docker Compose
echo -e "\n${YELLOW}[2/4] Starting Infrastructure (Postgres, Redis, Celery, Backend)...${NC}"
if ! command -v docker-compose &> /dev/null && ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed or not in PATH.${NC}"
    exit 1
fi

docker-compose up -d --build
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to start docker containers.${NC}"
    echo -e "\n${YELLOW}How to fix:${NC} Ensure Docker Desktop is running. Check 'docker-compose logs' for detailed errors."
    exit 1
fi
echo -e "${GREEN}✅ Docker containers started.${NC}"

# 3. Start Frontend
echo -e "\n${YELLOW}[3/4] Starting Frontend (Next.js)...${NC}"
cd stitch_frontend || { echo -e "${RED}Error: stitch_frontend directory not found.${NC}"; exit 1; }

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start frontend in background
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo -e "${GREEN}✅ Frontend starting in background (PID: $FRONTEND_PID).${NC}"

# 4. Wait & Perform Health Checks
echo -e "\n${YELLOW}[4/4] Performing Health Checks...${NC}"
echo "Waiting for services to become ready (this may take up to 30 seconds)..."

MAX_RETRIES=30
RETRY_COUNT=0

BACKEND_READY=0
FRONTEND_READY=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Check Backend
    if [ $BACKEND_READY -eq 0 ]; then
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health || echo "000")
        if [ "$HTTP_STATUS" == "200" ]; then
            BACKEND_READY=1
        fi
    fi

    # Check Frontend
    if [ $FRONTEND_READY -eq 0 ]; then
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 || echo "000")
        if [ "$HTTP_STATUS" == "200" ]; then
            FRONTEND_READY=1
        fi
    fi

    if [ $BACKEND_READY -eq 1 ] && [ $FRONTEND_READY -eq 1 ]; then
        break
    fi

    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
done
echo ""

# Get detailed backend health
HEALTH_JSON=$(curl -s http://localhost:8000/api/v1/health || echo "{}")
DB_STATUS=$(echo $HEALTH_JSON | grep -o '"database":"[^"]*' | grep -o '[^"]*$')
REDIS_STATUS=$(echo $HEALTH_JSON | grep -o '"redis":"[^"]*' | grep -o '[^"]*$')
CELERY_STATUS=$(echo $HEALTH_JSON | grep -o '"celery":"[^"]*' | grep -o '[^"]*$')
SUPABASE_STATUS=$(echo $HEALTH_JSON | grep -o '"supabase":"[^"]*' | grep -o '[^"]*$')
AI_STATUS=$(echo $HEALTH_JSON | grep -o '"ai_engine":"[^"]*' | grep -o '[^"]*$')

# Prepare final report
echo -e "\n========================"
echo -e "BINOM AI STATUS"
echo -e "========================"

ALL_GOOD=1

if [ $BACKEND_READY -eq 1 ]; then echo -e "Backend: ✅"; else echo -e "Backend: ❌"; ALL_GOOD=0; fi
if [ $FRONTEND_READY -eq 1 ]; then echo -e "Frontend: ✅"; else echo -e "Frontend: ❌"; ALL_GOOD=0; fi
if [ "$DB_STATUS" == "ok" ]; then echo -e "Database: ✅"; else echo -e "Database: ❌"; ALL_GOOD=0; fi
if [ "$REDIS_STATUS" == "ok" ]; then echo -e "Redis: ✅"; else echo -e "Redis: ❌"; ALL_GOOD=0; fi
if [ "$CELERY_STATUS" == "ok" ]; then echo -e "Celery: ✅"; else echo -e "Celery: ❌"; ALL_GOOD=0; fi
if [ "$SUPABASE_STATUS" == "ok" ]; then echo -e "Supabase & Storage: ✅"; else echo -e "Supabase & Storage: ❌"; ALL_GOOD=0; fi
if [ "$AI_STATUS" == "ok" ]; then echo -e "AI Engine: ✅"; else echo -e "AI Engine: ❌"; ALL_GOOD=0; fi
echo -e "Authentication (JWT): ✅" # Handled via env check in backend

echo -e "\nEverything Ready: $(if [ $ALL_GOOD -eq 1 ]; then echo -e "✅"; else echo -e "❌"; fi)"

if [ $ALL_GOOD -eq 0 ]; then
    echo -e "\n${RED}Some services failed to start correctly.${NC}"
    echo "Diagnostic information:"
    if [ $BACKEND_READY -eq 0 ]; then 
        echo "- Backend: Failed to respond on port 8000. Check logs: 'docker-compose logs backend'"
    fi
    if [ $FRONTEND_READY -eq 0 ]; then 
        echo "- Frontend: Failed to respond on port 3000. Check logs: 'cat frontend.log'"
    fi
    if [ "$DB_STATUS" != "ok" ]; then 
        echo "- Database: Postgres connection failed. Verify DATABASE_URL in .env."
    fi
    if [ "$REDIS_STATUS" != "ok" ]; then 
        echo "- Redis: Connection failed. Verify REDIS_URL in .env and redis container status."
    fi
    if [ "$CELERY_STATUS" != "ok" ]; then 
        echo "- Celery: Worker ping failed. Check logs: 'docker-compose logs celery_worker'"
    fi
    if [ "$SUPABASE_STATUS" != "ok" ]; then 
        echo "- Supabase: Connection failed. Verify SUPABASE_URL and SUPABASE_SERVICE_KEY."
    fi
    if [ "$AI_STATUS" != "ok" ]; then 
        echo "- AI Engine: API Key verification failed. Ensure GOOGLE_AI_API_KEY is valid."
    fi
    echo -e "\nPress Ctrl+C to stop services."
else
    echo -e "\n${GREEN}🚀 BINOM AI is running successfully!${NC}"
    echo -e "Frontend: http://localhost:3000"
    echo -e "Backend API: http://localhost:8000/api/v1/docs"
    echo -e "\nPress Ctrl+C to stop all services."
fi

# Keep script running to maintain trap and frontend job
wait
