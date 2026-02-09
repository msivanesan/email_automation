@echo off
if exist .venv (
    echo Virtual environment already exists.
) else (
    python -m venv .venv
)
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
pause
