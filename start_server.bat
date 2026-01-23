@echo off
cd /d "C:\Gráfica Rotativa\Projetos 2025\fila_impressao"
uvicorn server:app --host 0.0.0.0 --port 8000
