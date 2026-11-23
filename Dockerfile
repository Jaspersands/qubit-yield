FROM node:22-alpine AS dashboard
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
COPY artifacts/scenarios.json ../artifacts/scenarios.json
RUN npm run build

FROM python:3.12-slim AS application
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 QUBITYIELD_ROOT=/app MPLCONFIGDIR=/tmp/matplotlib
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY data/ ./data/
COPY artifacts/ ./artifacts/
COPY --from=dashboard /build/web/dist/ ./web/dist/
RUN useradd --create-home --uid 10001 qubityield
USER qubityield
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" || exit 1
CMD ["qubityield", "serve", "--host", "0.0.0.0", "--port", "8000"]

