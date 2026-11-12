#!/bin/sh
# Regenerate requirements.txt from pyproject.toml.
# Run with: docker compose run --rm compile
set -e
pip install --no-cache-dir pip-tools
pip-compile --strip-extras --output-file=requirements.txt pyproject.toml
