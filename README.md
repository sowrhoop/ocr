# Project 2 (Express)

Simple Express service with a minimal web page. Default port 9090.

## Build & Run

```sh
docker build -t project-2:dev .
docker run --rm -p 9090:9090 project-2:dev
open http://localhost:9090/
```

## Container Image (GHCR)

This repo ships with a GitHub Action that builds and pushes the image to GHCR:
- `ghcr.io/<owner>/project-2:latest`
- `ghcr.io/<owner>/project-2:<sha>`

