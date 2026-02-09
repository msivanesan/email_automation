if (Test-Path ".venv") {
    Write-Host "Virtual environment already exists."
} else {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

# Activate virtual environment
. ".\.venv\Scripts\Activate.ps1"

Write-Host "Installing dependencies..."
pip install -r requirements.txt

Write-Host "Starting Flask application..."
python app.py

Read-Host -Prompt "Press Enter to exit"
