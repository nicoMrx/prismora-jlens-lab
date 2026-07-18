FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .
EXPOSE 8000 8100
CMD ["python", "-m", "prismora_lab.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
