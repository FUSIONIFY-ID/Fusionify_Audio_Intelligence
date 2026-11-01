FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data/media /data/state && chown -R app:app /data
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .
USER app
ENV FAI_MEDIA_ROOT=/data/media FAI_STATE_ROOT=/data/state
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import os,urllib.request,urllib.parse; h=urllib.parse.urlsplit(os.environ.get('FAI_PUBLIC_BASE_URL','http://127.0.0.1:8000')).netloc; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/healthz',headers={'Host':h}),timeout=3)"
ENTRYPOINT ["fusionify-audio"]
CMD ["serve-http", "--host", "0.0.0.0", "--port", "8000"]
