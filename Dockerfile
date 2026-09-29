FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY api ./api
COPY flows ./flows

# pipeline leve na imagem para o endpoint /process/kpis responder já no primeiro start
RUN python -m src.generate_event_log --cases 120 --out data/event_log.csv \
 && python -m src.mining --out reports/mining.json \
 && mkdir -p bpmn dashboard

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"

CMD ["uvicorn", "src.automation_service:app", "--host", "0.0.0.0", "--port", "8080"]
