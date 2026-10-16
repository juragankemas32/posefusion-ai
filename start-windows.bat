@echo off
cd /d "%~dp0"
if not exist .venv (python -m venv .venv)
call .venv\Scripts\activate
pip install -r requirements.txt
if not exist .env (copy .env.example .env & echo Isi OPENAI_API_KEY di file .env sebelum Generate.)
python app.py
pause
