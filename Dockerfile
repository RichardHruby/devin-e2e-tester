FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY app app
COPY prompts prompts
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh
RUN mkdir -p /app/data && chown -R appuser /app
ENTRYPOINT ["/app/docker-entrypoint.sh"]
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
