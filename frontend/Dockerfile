# NACC SYS V3 — frontend image (Vite build served by nginx)
#
#   docker build -f frontend/Dockerfile \
#     --build-arg VITE_API_BASE_URL=https://api.example.org/api \
#     -t nacc-frontend ./frontend

# ---- build stage ---------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# npm ci needs both files and installs exactly what the lockfile pins.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines env vars at BUILD time, not run time — the API URL is compiled
# into the bundle, so it has to be a build arg. One image per environment.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- runtime stage -------------------------------------------------------
FROM nginx:1.27-alpine

# The nginx image runs envsubst over /etc/nginx/templates/*.template at boot,
# which is how ${PORT} reaches the config on platforms that assign one.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV PORT=8080

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider "http://127.0.0.1:${PORT}/" || exit 1
