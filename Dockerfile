FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CATERYA_HOME=/data CATERYA_HOST=0.0.0.0
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[api,crypto]" && useradd -m caterya && mkdir /data && chown caterya /data
USER caterya
VOLUME /data
EXPOSE 8080
HEALTHCHECK CMD python -c "import urllib.request as u;u.urlopen('http://127.0.0.1:8080/v1/health')"
CMD ["caterya", "serve"]
