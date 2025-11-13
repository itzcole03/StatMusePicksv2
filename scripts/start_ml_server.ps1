# Start the lightweight ML FastAPI app for local development
# Assumes the project's virtualenv is activated or available at .venv
if (Test-Path -Path .venv\Scripts\Activate.ps1) {
    & .venv\Scripts\Activate.ps1
}

# Run uvicorn on port 8001
uvicorn backend.main_ml:app --reload --port 8001
