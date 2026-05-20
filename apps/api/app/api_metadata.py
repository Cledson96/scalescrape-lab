OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "Endpoints simples para verificar disponibilidade e prontidao basica da API.",
    },
    {
        "name": "Observability",
        "description": "Metricas Prometheus e visoes operacionais usadas para demonstrar monitoramento do laboratorio.",
    },
    {
        "name": "Jobs",
        "description": "Criacao, consulta e retry de jobs de scraping publicados na fila para os workers Celery/Playwright.",
    },
    {
        "name": "Items",
        "description": "Consulta de dados extraidos e persistidos no PostgreSQL, com filtros por job e paginacao por fonte.",
    },
    {
        "name": "Sources",
        "description": "Operacoes administrativas sobre as fontes de scraping, como pausa e reativacao.",
    },
    {
        "name": "Proxies",
        "description": "Controle operacional dos perfis de proxy usados pelos workers para distribuicao de carga e cooldown.",
    },
    {
        "name": "Anti-Bot",
        "description": "Eventos do simulador anti-bot e sinais usados para explicar bloqueios, risco e desafios de captcha.",
    },
]

APP_DESCRIPTION = """
API do laboratorio **ScaleScrape Lab**, criada para demonstrar um pipeline de scraping distribuido com foco em:

- orquestracao de jobs via FastAPI + RabbitMQ + Celery;
- scraping browser-first com Playwright;
- persistencia de jobs, eventos e itens extraidos em PostgreSQL;
- cenarios controlados de login, captcha, anti-bot, retry, timeout, cooldown e proxy rotation;
- observabilidade com Prometheus, Grafana e historico operacional.

## Como usar na demo

1. Crie um job em `POST /jobs` para uma fonte suportada.
2. O job e gravado no banco e publicado na fila dos workers.
3. Consulte o andamento em `GET /jobs` ou `GET /jobs/{job_id}`.
4. Leia os dados persistidos em `GET /items`, `GET /items/page` ou `GET /jobs/{job_id}/items`.
5. Se precisar, reenvie uma execucao com `POST /jobs/{job_id}/retry`.

## Fontes suportadas no laboratorio

- `fake-target`: target protegido com login, sessao, captcha e anti-bot local;
- `books-to-scrape`: catalogo publico usado para demonstrar normalizacao de preco, nota e descricao;
- `globo-home`: noticias publicas com enriquecimento de metadados e imagem;
- `betano-football`: odds reais usadas para demonstrar scraping de layout dinamico.

## Endpoints uteis

- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`
- Metricas Prometheus: `/metrics`
"""
