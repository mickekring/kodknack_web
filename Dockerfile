# Two stages: Go turns content/ into a folder of HTML, Caddy serves that folder.
# Nothing from the build stage ships -- the running image contains a web server and
# static files, no toolchain, no application code, no database.

FROM golang:1.27-alpine AS build
WORKDIR /src

# Dependencies first so edits to content or templates don't invalidate the module cache.
COPY go.mod go.sum ./
RUN go mod download

COPY cmd ./cmd
COPY templates ./templates
COPY content ./content
COPY static ./static
COPY media ./media

# The only deployment-dependent value: it is baked into canonical links, og:url, the
# sitemap and robots.txt. Set it if the site is served from a different hostname.
ARG KODKNACK_BASE_URL=https://kodknack.kringen.se
RUN KODKNACK_BASE_URL="$KODKNACK_BASE_URL" go run ./cmd/build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/dist /srv

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -q --spider http://127.0.0.1/ || exit 1
