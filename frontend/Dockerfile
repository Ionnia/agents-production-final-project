# syntax=docker/dockerfile:1
# Frontend: build the Vite SPA, serve via nginx which reverse-proxies /api -> backend.
# Build context: ./frontend
FROM node:22-bookworm-slim AS build
WORKDIR /app
RUN corepack enable
# Deps first (cached unless manifests change)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
# Source + production build (mocks are always OFF in a build; client base URL is
# same-origin /api/v1, which nginx proxies to the backend)
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
