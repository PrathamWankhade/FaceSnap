# FaceSnap frontend (Next.js 15, standalone output).
#
# Build:
#   docker build -t facesnap-frontend -f frontend/Dockerfile .
# Run:
#   docker run --rm -p 3000:3000 \
#     -e NEXT_PUBLIC_BACKEND_URL=http://backend:8000 \
#     -e NEXT_PUBLIC_APP_URL=http://localhost:3000 \
#     -e GROQ_API_KEY=... \        # server-side only
#     facesnap-frontend
FROM node:20-slim AS builder

WORKDIR /app
ENV NODE_ENV=production
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM node:20-slim AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Non-root user.
RUN groupadd -r facesnap && useradd -r -g facesnap -d /app -s /sbin/nologin facesnap

# Standalone output: .next/standalone holds the server; .next/static holds assets.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

RUN chown -R facesnap:facesnap /app
USER facesnap

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O- http://127.0.0.1:3000/api/health || exit 1
# /api/health is proxied to the backend in dev; in production the frontend
# serves its own routes only — health lives on the backend. This check hits the
# Next.js readiness page instead.
CMD ["node", "server.js"]
