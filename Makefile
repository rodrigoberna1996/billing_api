.PHONY: run dev format lint test migrate upgrade downgrade

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

run:
	uvicorn app.main:create_app --factory --host $${API_HOST:-0.0.0.0} --port $${API_PORT:-8000} --reload

lint:
	ruff check app tests

format:
	ruff format app tests

test:
	pytest -q

migrate:
	alembic revision --autogenerate -m "manual"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1
