# Persia at War — one image serving the built game and the multiplayer sockets.
#
# Static hosting alone cannot run this: online play needs a live process, and
# both halves must share an origin so the WebSocket is same-origin. So the
# server serves dist/ and upgrades sockets on the same port.

FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# VITE_TEST_BUILD compiles in the in-app feedback widget. Drop it for a real
# release and the widget is absent from the bundle, not merely hidden.
ARG VITE_TEST_BUILD=1
ENV VITE_TEST_BUILD=$VITE_TEST_BUILD
RUN npm run build

FROM node:24-alpine AS run
WORKDIR /app
ENV NODE_ENV=production
# Only what the server needs at runtime: ws, plus the shared TypeScript it
# loads directly via Node's type stripping.
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
COPY server ./server
COPY src/sim/draftCore.ts src/sim/rng.ts ./src/sim/
COPY src/content/data ./src/content/data

ENV SERVE_DIST=1
ENV WS_PORT=8080
EXPOSE 8080

# The host restarts the container if this fails, so it must not sit behind the
# password gate.
HEALTHCHECK --interval=30s --timeout=4s --start-period=8s \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

CMD ["node", "server/index.ts"]
