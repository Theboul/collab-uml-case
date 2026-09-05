FROM python:3.12-slim

WORKDIR /workspace

# Copiar dependencias e instalarlas
COPY backend_case/pyproject.toml ./backend_case/
RUN pip install --no-cache-dir ./backend_case

# Copiar código del núcleo de dominio y del backend
COPY core/ ./core/
COPY backend_case/ ./backend_case/

ENV PYTHONPATH="/workspace:/workspace/backend_case"

WORKDIR /workspace/backend_case

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
