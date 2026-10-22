@echo off
cd /d "%~dp0code"
python -m streamlit run dashboard.py
pause
