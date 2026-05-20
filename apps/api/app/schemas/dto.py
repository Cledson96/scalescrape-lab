from datetime import datetime
from math import ceil
import os
from pydantic import BaseModel, Field, computed_field


def public_url_for(url: str):  # noqa: ANN201
    public_base = os.getenv("PUBLIC_TARGET_SITE_URL", "http://localhost:4000").rstrip("/")
    internal_base = "http://target-site:4000"
    if url.startswith(internal_base):
        return f"{public_base}{url.removeprefix(internal_base)}"
    return url


def public_api_url_for(path: str) -> str:
    public_base = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    return f"{public_base}/{path.lstrip('/')}"


def public_media_url(raw_data: dict) -> str | None:
    public_path = raw_data.get("image_public_path")
    if isinstance(public_path, str) and public_path:
        return public_api_url_for(public_path)

    image_path = raw_data.get("image_path")
    if not isinstance(image_path, str) or not image_path:
        return None

    media_root = os.getenv("MEDIA_ROOT", "/app/media").rstrip("/\\")
    normalized_image = image_path.replace("\\", "/")
    normalized_root = media_root.replace("\\", "/").rstrip("/")
    if normalized_image.startswith(normalized_root):
        relative_path = normalized_image.removeprefix(normalized_root).lstrip("/")
        return public_api_url_for(f"/media/{relative_path}")
    return None


class JobCreate(BaseModel):
    """Payload usado para iniciar um job de scraping pela API."""

    source: str = Field(
        default="fake-target",
        description="Nome logico da fonte a ser raspada.",
        examples=["fake-target", "books-to-scrape", "globo-home", "betano-football"],
    )
    start_url: str = Field(
        description="URL inicial que o worker deve abrir para comecar a coleta.",
        examples=["http://target-site:4000/protected/items?page=1"],
    )
    mode: str = Field(
        default="browser",
        description="Modo de execucao do worker. Neste laboratorio, o modo principal e `browser`.",
        examples=["browser"],
    )
    max_pages: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Quantidade maxima de paginas que o job pode visitar antes de encerrar.",
        examples=[1, 3, 10],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source": "fake-target",
                    "start_url": "http://target-site:4000/protected/items?page=1",
                    "mode": "browser",
                    "max_pages": 3,
                },
                {
                    "source": "books-to-scrape",
                    "start_url": "https://books.toscrape.com/catalogue/category/books/science-fiction_16/index.html",
                    "mode": "browser",
                    "max_pages": 1,
                },
            ]
        }
    }


class JobRead(BaseModel):
    """Representacao resumida de um job persistido e retornado pela API."""

    id: int = Field(description="Identificador unico do job.", examples=[42])
    source_id: int = Field(description="Identificador interno da fonte associada ao job.", examples=[1])
    start_url: str = Field(description="URL inicial efetivamente salva para a coleta.")
    status: str = Field(description="Estado atual do job, como pending, running, success ou failed.", examples=["success"])
    mode: str = Field(description="Modo de execucao do job.", examples=["browser"])
    max_pages: int = Field(description="Limite de paginas permitido para a execucao.", examples=[3])
    attempts: int = Field(description="Numero de tentativas ja realizadas para o job.", examples=[1])
    items_found: int = Field(description="Quantidade de itens persistidos para o job.", examples=[12])
    error_message: str | None = Field(description="Mensagem de erro, caso a execucao tenha falhado ou sido bloqueada.", default=None)
    created_at: datetime = Field(description="Data/hora de criacao do job no banco.")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 42,
                    "source_id": 1,
                    "start_url": "http://target-site:4000/protected/items?page=1",
                    "status": "success",
                    "mode": "browser",
                    "max_pages": 3,
                    "attempts": 1,
                    "items_found": 12,
                    "error_message": None,
                    "created_at": "2026-05-18T21:52:13.392016",
                    "public_url": "https://dev.scalescrape.cledson.com.br/protected/items?page=1",
                }
            ]
        },
    }

    @computed_field(description="Versao publica da URL inicial, trocando o host interno pelo dominio exposto da demo.")
    @property
    def public_url(self) -> str:
        return public_url_for(self.start_url)


class ScrapedItemRead(BaseModel):
    """Item extraido e normalizado pelo worker."""

    id: int = Field(description="Identificador unico do item persistido.", examples=[99])
    job_id: int = Field(description="Job responsavel por gerar este item.", examples=[17])
    external_id: str = Field(description="Identificador externo ou slug do registro na fonte original.")
    title: str = Field(description="Titulo principal exibido no dashboard e nos resultados da API.")
    detail_url: str = Field(description="URL de detalhe original usada pelo scraper ou salva no item.")
    raw_data: dict = Field(description="Payload bruto normalizado com campos especificos da fonte, como preco, odds, resumo, categoria ou imagem.")
    created_at: datetime = Field(description="Horario em que o item foi salvo no banco.")
    extracted_at: datetime = Field(description="Horario em que a coleta do item foi concluida.")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 99,
                    "job_id": 17,
                    "external_id": "join_902",
                    "title": "Join",
                    "detail_url": "https://books.toscrape.com/catalogue/join_902/index.html",
                    "raw_data": {
                        "source": "books-to-scrape",
                        "price": {"formatted": "£35.67", "brl_formatted": "R$ 231,86"},
                        "rating": {"label": "Five", "value": 5},
                        "description": "What if you could live multiple lives simultaneously?",
                    },
                    "created_at": "2026-05-18T21:39:14.229704",
                    "extracted_at": "2026-05-18T21:39:14.229704",
                    "public_detail_url": "https://books.toscrape.com/catalogue/join_902/index.html",
                    "public_image_url": None,
                }
            ]
        },
    }

    @computed_field(description="Versao publica da URL de detalhe, adequada para abrir no dominio da demo ou no site publico original.")
    @property
    def public_detail_url(self) -> str:
        return public_url_for(self.detail_url)

    @computed_field(description="URL publica da imagem servida pela API, quando a fonte salva midia localmente.")
    @property
    def public_image_url(self) -> str | None:
        return public_media_url(self.raw_data)


class ScrapedItemPageRead(BaseModel):
    """Resposta paginada usada pelo dashboard e por consultas filtradas por fonte."""

    items: list[ScrapedItemRead] = Field(description="Itens retornados na pagina atual.")
    total: int = Field(description="Quantidade total de itens encontrados para o filtro informado.", examples=[87])
    page: int = Field(description="Pagina atual retornada pela API.", examples=[2])
    page_size: int = Field(description="Quantidade de itens por pagina.", examples=[10])

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [],
                    "total": 87,
                    "page": 2,
                    "page_size": 10,
                    "total_pages": 9,
                }
            ]
        }
    }

    @computed_field(description="Quantidade total de paginas calculada automaticamente a partir de total e page_size.")
    @property
    def total_pages(self) -> int:
        if self.total == 0:
            return 0
        return ceil(self.total / self.page_size)


class SourceRead(BaseModel):
    """Fonte configurada para scraping e controle operacional."""

    id: int = Field(description="Identificador interno da fonte.", examples=[1])
    name: str = Field(description="Nome logico da fonte.", examples=["fake-target"])
    base_url: str = Field(description="URL base associada a fonte.")
    status: str = Field(description="Status operacional da fonte.", examples=["active"])
    circuit_open_until: datetime | None = Field(description="Horario ate o qual o circuito fica aberto, quando aplicavel.", default=None)

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "fake-target",
                    "base_url": "http://target-site:4000/protected/items?page=1",
                    "status": "active",
                    "circuit_open_until": None,
                }
            ]
        },
    }


class ProxyRead(BaseModel):
    """Proxy operacional usado para distribuir carga e isolar bloqueios."""

    id: int = Field(description="Identificador interno do proxy.", examples=[2])
    name: str = Field(description="Nome amigavel do proxy.", examples=["proxy-b"])
    status: str = Field(description="Status atual do proxy.", examples=["cooldown"])
    current_active_jobs: int = Field(description="Quantidade atual de jobs ativos usando este proxy.", examples=[1])
    max_concurrent_jobs: int = Field(description="Limite maximo configurado para concorrencia neste proxy.", examples=[3])
    cooldown_until: datetime | None = Field(description="Horario de termino do cooldown, quando o proxy esta temporariamente fora de uso.", default=None)

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 2,
                    "name": "proxy-b",
                    "status": "cooldown",
                    "current_active_jobs": 0,
                    "max_concurrent_jobs": 3,
                    "cooldown_until": "2026-05-18T22:55:00.000000",
                }
            ]
        },
    }

