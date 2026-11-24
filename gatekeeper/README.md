# Gatekeeper (Android)

The Android app lives in this directory. It is a separate build: `docker compose` does not build or start it.

## Talking to core

- Core's API is at `http://127.0.0.1:8000` by default. Its interactive docs are at `/docs`.
- To reach core from the demo phone on the same network, set `BIND_ADDR=0.0.0.0` in `.env` and restart the stack.
- Use `BIND_ADDR=0.0.0.0` for the demo phone only. It exposes core to the whole network, so set it back afterwards.

## Handling a pending verdict

`POST /v1/check` can return `pending`. This means there is no verdict yet. It never means safe.

- Poll `GET /v1/check/{id}` until a verdict arrives.
- Treat `pending` the way ARCHITECTURE.md section 3 treats a timeout: if the local score is low, forward the link. Otherwise show the "Checking link" screen for up to 3 s, then warn with what is known.
