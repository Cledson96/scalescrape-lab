from collections import deque
from time import sleep
from uuid import uuid4

from fastapi import Cookie, FastAPI, Header, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.antibot import AntibotAction, AntibotSimulator
from app.captcha import CaptchaStore
from app.fake_data import find_record, get_external_records, get_local_records, paginate_records
from app.views import (
    render_challenge_page,
    render_detail_page,
    render_home,
    render_items_page,
    render_layout_changed_page,
)

app = FastAPI(title="ScaleScrape Lab Target Site", version="0.1.0")
antibot = AntibotSimulator()
captcha_store = CaptchaStore()
antibot_events: deque[dict] = deque(maxlen=200)


class CaptchaVerifyPayload(BaseModel):
    challenge_id: str
    answer: str
    session_id: str
    proxy_id: str = "direct"


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(render_home(local_total=240, external_total=500))


@app.get("/items", response_class=HTMLResponse)
def items(page: int = 1) -> HTMLResponse:
    records = get_local_records(prefix="normal", total=240)
    current_page = paginate_records(records, page_number=page, per_page=12)
    return HTMLResponse(
        render_items_page(
            title="Dataset publico sintetico",
            subtitle="Fonte local estavel para scraping paginado.",
            page=current_page,
            route="/items",
            detail_route="/items",
        )
    )


@app.get("/items/{item_id}", response_class=HTMLResponse)
def item_detail(item_id: str) -> HTMLResponse:
    return HTMLResponse(render_detail_page(find_record(item_id)))


@app.get("/external/items", response_class=HTMLResponse)
def external_items(page: int = 1) -> HTMLResponse:
    records = list(get_external_records(size=500))
    current_page = paginate_records(records, page_number=page, per_page=12)
    return HTMLResponse(
        render_items_page(
            title="Fonte fake externa em massa",
            subtitle="RandomUser normalizado com cache e fallback local.",
            page=current_page,
            route="/external/items",
            detail_route="/external/items",
        )
    )


@app.get("/external/items/{item_id}", response_class=HTMLResponse)
def external_item_detail(item_id: str) -> HTMLResponse:
    return HTMLResponse(render_detail_page(find_record(item_id)))


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
        return HTMLResponse(render_challenge_page(challenge.challenge_id))

    records = get_local_records(prefix="protected", total=240)
    current_page = paginate_records(records, page_number=page, per_page=12)
    return HTMLResponse(
        render_items_page(
            title="Dataset protegido",
            subtitle="Mesmo conteudo sintetico sob avaliacao anti-bot local.",
            page=current_page,
            route="/protected/items",
            detail_route="/items",
        )
    )


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
    records = get_local_records(prefix="unstable", total=120)
    current_page = paginate_records(records, page_number=page, per_page=12)
    return HTMLResponse(
        render_items_page(
            title="Fonte instavel",
            subtitle="Paginas pares retornam erro 500 para validar retry.",
            page=current_page,
            route="/unstable/items",
            detail_route="/items",
        )
    )


@app.get("/layout-changed/items", response_class=HTMLResponse)
def layout_changed_items() -> HTMLResponse:
    return HTMLResponse(render_layout_changed_page())


@app.get("/antibot/debug/session")
def debug_antibot() -> list[dict]:
    return list(antibot_events)

