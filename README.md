# ScaleScrape Lab Python

Laboratorio controlado de scraping em escala com Python, RabbitMQ, Playwright,
PostgreSQL, Prometheus, Grafana, anti-bot simulator, proxy rotation local e
captcha proprio resolvido opcionalmente via 2Captcha.

O objetivo e mostrar arquitetura de scraping em producao: filas, workers,
controle de concorrencia, retry/backoff, DLQ, circuit breaker, politicas de
seguranca, metricas e observabilidade. Tudo roda contra um target-site local do
proprio projeto.

## Arquitetura

```text
Usuario / Swagger
        ↓
FastAPI API
        ↓
PostgreSQL
        ↓
RabbitMQ
        ↓
Celery Workers
        ↓
Playwright
        ↓
Proxy Manager
        ↓
Target Site Fake
        ↓
Anti-Bot Simulator
        ↓
Captcha proprio
        ↓
2Captcha somente se habilitado e permitido por whitelist
```

## Stack

- Python + FastAPI para API e target-site
- Celery + RabbitMQ para filas
- Playwright Python para scraping
- PostgreSQL com SQLAlchemy
- Prometheus + Grafana para monitoramento
- 2Captcha somente para captcha proprio/local
- Docker Compose para infraestrutura local
- `unittest` para validacoes de policy e simuladores

## Como Rodar

```bash
cp .env.example .env
docker compose up --build
```

Servicos:

- API: http://localhost:8000/docs
- Target-site: http://localhost:4000
- RabbitMQ UI: http://localhost:15672
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## Como Criar Um Job

No Swagger (`/docs`), execute `POST /jobs`:

```json
{
  "source": "fake-target",
  "start_url": "http://target-site:4000/protected/items?page=1",
  "mode": "browser",
  "max_pages": 3
}
```

Outros cenarios:

```text
http://target-site:4000/items?page=1
http://target-site:4000/rate-limited/items?page=1
http://target-site:4000/forbidden/items?page=1
http://target-site:4000/unstable/items?page=1
http://target-site:4000/layout-changed/items?page=1
```

## Captcha Local Com 2Captcha

Por padrao, o projeto usa `MockCaptchaResolverProvider`.

Para demonstrar 2Captcha real no captcha proprio/local:

```env
ENABLE_REAL_2CAPTCHA=true
TWO_CAPTCHA_API_KEY=sua_chave
ALLOWED_CAPTCHA_HOSTS=target-site,localhost,127.0.0.1
MAX_CAPTCHA_SOLVES_PER_RUN=20
```

O provider valida o host antes de chamar a API externa. Se o host nao estiver na
whitelist, o job e bloqueado por policy.

## Proxy Rotation Local

Na v1, proxies sao simulados por header interno:

```text
X-Lab-Proxy-Id: proxy-a
X-Lab-Proxy-Id: proxy-b
X-Lab-Proxy-Id: proxy-c
```

O target-site usa esse header apenas em ambiente local para simular IPs
diferentes e calcular risco por proxy. Proxies com muitos `403` ou `429` entram
em cooldown.

## Regras De Seguranca

Este projeto pode:

- usar 2Captcha apenas contra captcha proprio/local
- simular anti-bot no target-site proprio
- simular proxy rotation em ambiente local
- simular 403, 429, timeout e challenge
- demonstrar arquitetura de scraping em escala

Este projeto nao faz:

- bypass de Cloudflare real
- resolucao de captcha de terceiros
- proxy rotation contra sites reais
- coleta de dados pessoais reais
- scraping agressivo em sites reais
- tentativa de esconder automacao de sistemas reais

## Testes

Sem Docker, e possivel validar as regras puras com o Python local:

```powershell
python -m unittest discover -s tests -v
```

No ambiente Codex, foi usado o Python embutido:

```powershell
& "C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```

