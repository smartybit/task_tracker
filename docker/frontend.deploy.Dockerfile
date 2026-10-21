FROM node:22-bookworm-slim AS build
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node frontend/package*.json ./
RUN npm ci
COPY --chown=node:node frontend/ ./
ARG APP_BASE_PATH=/
ARG INSTANCE_ID=task-tracker-dev
ENV APP_BASE_PATH=$APP_BASE_PATH INSTANCE_ID=$INSTANCE_ID
RUN node --experimental-strip-types scripts/write-instance-config.mjs && npm run build
RUN node --experimental-strip-types scripts/deployment-config.mjs

FROM nginxinc/nginx-unprivileged:stable-alpine
COPY --from=build /app/deployment-root/ /usr/share/nginx/html/
COPY --from=build /app/nginx.conf.template /etc/task-tracker/nginx.conf.template
COPY --from=build /app/instance.env /etc/task-tracker/instance.env
COPY --chmod=755 docker/frontend-start.sh /usr/local/bin/task-tracker-frontend
ENTRYPOINT ["/usr/local/bin/task-tracker-frontend"]
