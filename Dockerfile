FROM python:3.12-alpine AS builder

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && find /opt/venv -depth -type d -name __pycache__ -exec rm -rf {} + \
    && rm -rf /opt/venv/lib/python3.12/site-packages/pip \
              /opt/venv/lib/python3.12/site-packages/pip-*.dist-info \
              /opt/venv/bin/pip /opt/venv/bin/pip3 /opt/venv/bin/pip3.12

FROM python:3.12-alpine AS runtime

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN addgroup --system appuser && adduser --system --no-create-home --ingroup appuser appuser

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser . .
RUN chmod +x docker-entrypoint.sh

USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
