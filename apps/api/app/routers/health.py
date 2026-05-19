from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Verifica a saude basica da API",
    description="Usado para readiness/liveness checks do container e para validacao rapida de disponibilidade da API.",
    response_description="Status simples indicando que a API respondeu com sucesso.",
)
def health() -> dict[str, str]:
    return {"status": "ok"}
