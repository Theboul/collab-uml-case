FROM python:3.12-slim

WORKDIR /workspace

# Copiar dependencias e instalarlas
COPY backend_case/requirements.txt ./backend_case/
RUN pip install --no-cache-dir -r ./backend_case/requirements.txt

# Copiar código del núcleo de dominio y del backend
COPY core/ ./core/
COPY backend_case/ ./backend_case/

ENV PYTHONPATH="/workspace:/workspace/backend_case"

WORKDIR /workspace/backend_case

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--ws-max-size", "8192"]
