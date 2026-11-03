FROM node:22-bookworm-slim AS ui-build
WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1 COPILOTKIT_TELEMETRY_DISABLED=true
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 COPILOTKIT_TELEMETRY_DISABLED=true \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PROOF_DATA_DIR=/var/data/proof
COPY --from=ui-build /usr/local/bin/node /usr/local/bin/node
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY --from=ui-build /build/.next/standalone ./frontend
COPY --from=ui-build /build/.next/static ./frontend/.next/static
COPY adapters ./adapters
COPY api ./api
COPY core ./core
COPY runners ./runners
COPY workflows ./workflows
COPY app.py composition.py ./
COPY scripts/serve_hosted.py ./scripts/serve_hosted.py
EXPOSE 10000
CMD ["python", "scripts/serve_hosted.py"]
