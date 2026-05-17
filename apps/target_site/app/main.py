from collections import deque
from time import sleep
from uuid import uuid4

from fastapi import Cookie, FastAPI, Header, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.antibot import AntibotAction, AntibotSimulator
from app.captcha import CaptchaStore

app = FastAPI(title="ScaleScrape Lab Target Site", version="0.1.0")
antibot = AntibotSimulator()
captcha_store = CaptchaStore()
antibot_events: deque[dict] = deque(maxlen=200)


class CaptchaVerifyPayload(BaseModel):
    challenge_id: str
    answer: str
    session_id: str
    proxy_id: str = "direct"


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="pt-BR">
          <head>
            <meta charset="utf-8" />
            <title>{title}</title>
          </head>
          <body>
            <main>{body}</main>
          </body>
        </html>
        """
    )


def render_items(prefix: str, page_number: int, protected: bool = False) -> HTMLResponse:
    items = []
    for index in range(1, 6):
        item_id = ((page_number - 1) * 5) + index
        items.append(
            f"""
            <article class="item-card" data-item-id="{prefix}-{item_id}">
              <h2 class="item-title">Registro publico {item_id}</h2>
              <a class="detail-link" href="/items/{prefix}-{item_id}">Detalhe</a>
            </article>
            """
        )
    next_link = ""
    if page_number < 3:
        route = "/protected/items" if protected else "/items"
        next_link = f'<a class="next-page" href="{route}?page={page_number + 1}">Proxima</a>'
    return page("ScaleScrape Target", "\n".join(items) + next_link)


@app.get("/items", response_class=HTMLResponse)
def items(page: int = 1) -> HTMLResponse:
    return render_items("normal", page)


@app.get("/items/{item_id}", response_class=HTMLResponse)
def item_detail(item_id: str) -> HTMLResponse:
    return page(
        "Detalhe",
        f"""
        <section class="item-detail" data-item-id="{item_id}">
          <h1>Detalhe {item_id}</h1>
          <p class="status">Fonte publica simulada</p>
        </section>
        """,
    )


@app.get("/protected/items", response_class=HTMLResponse)
def protected_items(
    response: Response,
    page: int = 1,
    user_agent: str | None = Header(default=None),
    proxy_id: str = Header(default="direct", alias="X-Lab-Proxy-Id"),
    lab_session: str | None = Cookie(default=None),
    lab_clearance: str | None = Cookie(default=None),
) -> HTMLResponse:
    session_id = lab_session or str(uuid4())
    response.set_cookie("lab_session", session_id, httponly=True)
    decision = antibot.evaluate(
        session_id=session_id,
        proxy_id=proxy_id,
        path="/protected/items",
        user_agent=user_agent,
        has_clearance_cookie=lab_clearance == "ok",
    )
    antibot_events.append(
        {
            "session_id": session_id,
            "proxy_id": proxy_id,
            "risk_score": decision.risk_score,
            "action": decision.action.value,
            "reason": decision.reason,
        }
    )

    if decision.action == AntibotAction.RATE_LIMIT:
        raise HTTPException(status_code=429, detail=decision.reason)
    if decision.action == AntibotAction.FORBID:
        raise HTTPException(status_code=403, detail=decision.reason)
    if decision.action == AntibotAction.DELAY:
        sleep(0.4)
    if decision.action == AntibotAction.CHALLENGE:
        challenge = captcha_store.create()
        return page(
            "Challenge",
            f"""
            <section id="captcha-challenge" data-challenge-id="{challenge.challenge_id}">
              <h1>Verificacao local</h1>
              <img id="captcha-image" src="/captcha/image/{challenge.challenge_id}" alt="captcha local" />
              <p>Este captcha pertence ao proprio laboratorio.</p>
            </section>
            """,
        )

    return render_items("protected", page, protected=True)


@app.get("/captcha/image/{challenge_id}")
def captcha_image(challenge_id: str) -> Response:
    try:
        payload = captcha_store.render_png(challenge_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="challenge_not_found") from exc
    return Response(payload, media_type="image/png")


@app.post("/captcha/verify")
def verify_captcha(payload: CaptchaVerifyPayload, response: Response) -> dict[str, bool]:
    if captcha_store.verify(payload.challenge_id, payload.answer):
        response.set_cookie("lab_clearance", "ok", httponly=True)
        return {"ok": True}
    antibot.record_captcha_error(payload.session_id, payload.proxy_id)
    return {"ok": False}


@app.get("/rate-limited/items")
def rate_limited_items() -> None:
    raise HTTPException(status_code=429, detail="rate limit simulado")


@app.get("/forbidden/items")
def forbidden_items() -> None:
    raise HTTPException(status_code=403, detail="bloqueio simulado")


@app.get("/unstable/items", response_class=HTMLResponse)
def unstable_items(page: int = 1) -> HTMLResponse:
    if page % 2 == 0:
        raise HTTPException(status_code=500, detail="erro intermitente simulado")
    return render_items("unstable", page)


@app.get("/layout-changed/items", response_class=HTMLResponse)
def layout_changed_items() -> HTMLResponse:
    return page(
        "Layout alterado",
        """
        <section class="changed-layout">
          <div data-record="layout-1">Registro sem seletores esperados</div>
        </section>
        """,
    )


@app.get("/antibot/debug/session")
def debug_antibot() -> list[dict]:
    return list(antibot_events)

