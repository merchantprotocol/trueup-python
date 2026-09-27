# TrueUp Python SDK. Everything runs in Docker.

default:
    @just --list

# build and run the tests in Docker (live API tests need TRUEUP_API_KEY)
test:
    docker compose build test
    docker compose run --rm test
