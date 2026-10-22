@echo off
cd /d "%~dp0code"
python make_crops.py
python run_experiments.py
python analyze.py
python downstream.py
pause
