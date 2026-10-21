FROM node:22-bookworm-slim
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node frontend/package*.json ./
RUN npm ci
COPY --chown=node:node frontend/ ./
ARG APP_BASE_PATH=/
ARG INSTANCE_ID=task-tracker-dev
ENV APP_BASE_PATH=$APP_BASE_PATH INSTANCE_ID=$INSTANCE_ID
RUN node --experimental-strip-types scripts/write-instance-config.mjs
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
