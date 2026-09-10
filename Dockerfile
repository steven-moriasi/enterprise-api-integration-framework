FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --upgrade pip==26.2.1 \
    && pip install .

FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS runtime

ENV PATH="/opt/venv/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

RUN groupadd --system --gid 1001 integration \
    && useradd --system --uid 1001 --gid integration integration

WORKDIR /app

COPY --from=build /opt/venv /opt/venv

USER integration

EXPOSE 8003

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8003/health', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
