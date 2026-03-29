#!/bin/bash
# run_api.sh — Start the MJ Realty Coaching API
# Usage: ./run_api.sh

cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
