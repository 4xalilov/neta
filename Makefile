up: ; docker compose up -d
down: ; docker compose down
test: ; docker compose exec api pytest -q
eval: ; docker compose exec api python -m engine.evals.run
migrate: ; docker compose exec api alembic upgrade head
