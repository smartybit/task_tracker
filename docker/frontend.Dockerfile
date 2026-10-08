FROM node:22-bookworm-slim
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node frontend/package*.json ./
RUN npm ci
COPY --chown=node:node frontend/ ./
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
