FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libxml2-dev libxslt1-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
ENV PYTHONPATH=/srv/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "api:app", "--app-dir", "/srv/app", "--host", "0.0.0.0", "--port", "8000"]
