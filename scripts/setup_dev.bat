@echo off
REM Development environment setup script for Windows

echo ===== Kirby Development Setup =====
echo.

echo Step 1: Creating virtual environment...
python -m venv venv

echo Step 2: Activating virtual environment...
call venv\Scripts\activate.bat

echo Step 3: Upgrading pip...
python -m pip install --upgrade pip

echo Step 4: Installing Kirby with dev dependencies...
pip install -e ".[dev]"

echo.
echo ===== Setup Complete! =====
echo.
echo To activate the virtual environment:
echo   venv\Scripts\activate.bat
echo.
echo To run tests:
echo   python scripts\run_tests.py
echo.
echo To start the database:
echo   docker compose up -d timescaledb
echo.
pause
