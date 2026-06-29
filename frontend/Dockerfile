# Frontend image — multi-stage build producing a self-contained standalone
# Next.js server (no external CDN assets, suitable for air-gapped hosting).
FROM node:20-slim AS builder
WORKDIR /app

RUN npm install -g pnpm@9
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .

# Backend URL the browser will call; baked at build time.
ARG NEXT_PUBLIC_API_URL=http://localhost:5167
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
