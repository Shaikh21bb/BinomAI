.PHONY: start stop logs clean db-shell redis-shell install

# Start the entire BINOM AI project
start:
	@chmod +x start.sh
	@./start.sh

# Stop the entire BINOM AI project
stop:
	@echo "Stopping Docker containers..."
	@docker-compose down
	@echo "Checking for running frontend processes..."
	@pkill -f "next" || echo "No frontend running."
	@echo "BINOM AI stopped."

# View logs for all docker services
logs:
	@docker-compose logs -f

# Clean up all containers, volumes, and node_modules
clean:
	@echo "Cleaning up Docker..."
	@docker-compose down -v --remove-orphans
	@echo "Removing frontend node_modules..."
	@rm -rf stitch_frontend/node_modules stitch_frontend/.next
	@echo "Cleanup complete."

# Access database shell
db-shell:
	@docker exec -it binom_postgres psql -U postgres

# Access redis shell
redis-shell:
	@docker exec -it binom_redis redis-cli

# Install dependencies (if you don't want to start right away)
install:
	@cd stitch_frontend && npm install
