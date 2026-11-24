from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from playwright.async_api import async_playwright
from pydantic import BaseModel

from app.capture import BROWSER_ARGS, CaptureResponse, InternalHost, InvalidUrl, NavigationFailed, capture


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_playwright() as playwright:
        app.state.browser = await playwright.chromium.launch(args=BROWSER_ARGS)
        yield
        await app.state.browser.close()


app = FastAPI(lifespan=lifespan)


class CaptureRequest(BaseModel):
    url: str


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/capture")
async def capture_endpoint(body: CaptureRequest, request: Request) -> CaptureResponse:
    try:
        return await capture(request.app.state.browser, body.url)
    except (InvalidUrl, InternalHost) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NavigationFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
