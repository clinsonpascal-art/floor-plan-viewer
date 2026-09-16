@echo off
cd /d "%~dp0..\backend"
if not exist .venv\Scripts\python.exe (
  py -m venv .venv
  call .venv\Scripts\activate
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
set PYTHONPATH=.
set LUXE_PROVIDER=mock
set LUXE_OUT_DIR=./renders_demo
python -m app.pipeline --unit continuum-residence-01 --plan .\source_continuum_residence_01.jpg
python -m uvicorn app.main:app --reload
