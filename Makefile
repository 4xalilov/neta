up: ; docker compose up -d
up-gpu: ; docker compose --profile gpu up -d
down: ; docker compose down
logs: ; docker compose logs -f
test: ; docker compose exec api pytest -q
test-local: ; \
	cd apps/api && python -m pytest -q && \
	cd ../render && npm test
eval: ; docker compose exec api python -m engine.evals.run
eval-local: ; cd apps/api && .venv/bin/python -m engine.evals.run --fake
migrate: ; docker compose exec api alembic upgrade head
lint: ; ruff check apps/api && ruff format --check apps/api
fmt: ; ruff format apps/api
shell: ; docker compose exec api bash
