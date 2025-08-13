.PHONY: run docker-up docker-down

run:
	python -m bot.main

docker-up:
	docker compose up -d

docker-down:
	docker compose down
