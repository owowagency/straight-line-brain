FROM node:20-alpine AS base
RUN npm i -g pnpm

# Install dependencies
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Build
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# AUTH_SECRET must match at build and runtime for next-auth JWT
ARG AUTH_SECRET=e3b0c44298fc1c149afbf4c8996fb924
ENV AUTH_SECRET=${AUTH_SECRET}
RUN pnpm build

# Production
FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
