FROM node:26-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

ARG VITE_AUTH_MODE=oidc
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_OIDC_AUTHORITY
ARG VITE_OIDC_CLIENT_ID
ARG VITE_OIDC_REDIRECT_URI
ARG VITE_OIDC_SCOPE="openid profile"
ENV VITE_AUTH_MODE=${VITE_AUTH_MODE} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_OIDC_AUTHORITY=${VITE_OIDC_AUTHORITY} \
    VITE_OIDC_CLIENT_ID=${VITE_OIDC_CLIENT_ID} \
    VITE_OIDC_REDIRECT_URI=${VITE_OIDC_REDIRECT_URI} \
    VITE_OIDC_SCOPE=${VITE_OIDC_SCOPE}

RUN if [ "${VITE_AUTH_MODE}" = "oidc" ]; then \
      test -n "${VITE_OIDC_AUTHORITY}" && test -n "${VITE_OIDC_CLIENT_ID}"; \
    fi \
    && npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY deploy/nginx/security-headers.inc /etc/nginx/conf.d/security-headers.inc
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:8080/frontend-health"]
