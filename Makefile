.PHONY: dev test lint fmt docker down migrate admin train install

install:
	pip install -r requirements-dev.txt

dev:            ## run locally with auto-reload
	python -m alembic upgrade head && python -m uvicorn backend.main:app --reload --port 8000

test:
	python -m pytest tests -q

lint:
	python -m ruff check .

fmt:
	python -m ruff check . --fix

docker:         ## app + PostgreSQL
	docker compose up --build

down:
	docker compose down

migrate:
	python -m alembic upgrade head

admin:          ## make EMAIL=you@x.org NAME="Your Name" admin
	python scripts/create_admin.py --email $(EMAIL) --name "$(NAME)"

train:          ## retrain predictor from real outcomes (needs >= 50)
	python scripts/train_predictor.py
