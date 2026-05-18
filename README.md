# ScaleScrape Lab

Laboratorio controlado de scraping em escala com Python, RabbitMQ, Playwright,
PostgreSQL, Prometheus, Grafana, target-site em Next.js/TypeScript, anti-bot
simulator, proxy rotation local e captcha proprio resolvido opcionalmente via
2Captcha.

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

- Python + FastAPI para API de orquestracao
- Next.js 16 + TypeScript para target-site fake visual
- Celery + RabbitMQ para filas
- Playwright Python para scraping
- PostgreSQL com SQLAlchemy
- Prometheus + Grafana para monitoramento
- 2Captcha somente para captcha proprio/local
- Docker Compose para infraestrutura local
- `unittest` para policies do worker
- Node test runner + TypeScript para dataset, anti-bot e componentes do target-site

## Como Rodar

```bash
cp .env.example .env
docker compose up --build
```

Servicos:

- API: http://localhost:8000/docs
- Target-site visual: http://localhost:4000
- RabbitMQ UI: http://localhost:15672
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## Target-Site Visual Em Next.js

O target-site e uma vitrine local do simulador em Next.js 16 com App Router. O
visual foi inspirado na linguagem de protecao ao credito, prevencao a fraudes,
onboarding e monitoramento continuo usada pela Procob, sem copiar assets
proprietarios. A home (`/`) mostra os cenarios disponiveis e as paginas de dados
preservam os seletores usados pelo Playwright:

- `/items?page=1`: dataset local sintetico, paginado e estavel
- `/login?next=/protected/items?page=1`: login fake com captcha local
- `/protected/items?page=1`: dataset sob login, anti-bot local, session, risco e challenge
- `/external/items?page=1`: massa fake externa via RandomUser, com fallback local
- `/rate-limited/items`: resposta `429` para testar retry e cooldown
- `/forbidden/items`: resposta `403` para testar bloqueio
- `/unstable/items?page=1`: paginas pares retornam `500`
- `/layout-changed/items`: pagina sem `.item-card` para testar quebra de seletor

A fonte externa usa dados fake normalizados e nao expoe e-mail, telefone ou
documento. Se a API externa estiver indisponivel, o simulador usa uma massa
local deterministica para manter a demo funcionando.

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
http://target-site:4000/external/items?page=1
http://target-site:4000/rate-limited/items?page=1
http://target-site:4000/forbidden/items?page=1
http://target-site:4000/unstable/items?page=1
http://target-site:4000/layout-changed/items?page=1
```

## Captcha Local Com 2Captcha

Por padrao, o projeto usa `MockCaptchaResolverProvider`. O target-site exige
login em `/protected/items`; o worker detecta `#login-form`, preenche
`TARGET_SITE_USERNAME` e `TARGET_SITE_PASSWORD`, resolve `#captcha-image` e
continua a raspagem dos `.item-card`.

Credenciais demo:

```env
TARGET_SITE_USERNAME=demo
TARGET_SITE_PASSWORD=demo123
```

Para demonstrar 2Captcha real no captcha proprio/local:

```env
ENABLE_REAL_2CAPTCHA=true
TWO_CAPTCHA_API_KEY=sua_chave
ALLOWED_CAPTCHA_HOSTS=target-site,localhost,127.0.0.1
MAX_CAPTCHA_SOLVES_PER_RUN=20
```

O provider valida o host antes de chamar a API externa. Se o host nao estiver na
whitelist, o job e bloqueado por policy.

## Deploy Na VPS

O deploy usa `compose.deploy.yml` com imagens GHCR:

- `ghcr.io/cledson96/scalescrape-lab-api`
- `ghcr.io/cledson96/scalescrape-lab-worker`
- `ghcr.io/cledson96/scalescrape-lab-target-site`

Workflows:

- `.github/workflows/deploy-development.yml`: branch `development`, tags `development` e `development-${sha}`
- `.github/workflows/deploy-production.yml`: branch `main`, tags `latest` e `${sha}`

Subdominios planejados:

- Dev: `dev.scalescrape.cledson.com.br`, `api-dev.scalescrape.cledson.com.br`, `grafana-dev.scalescrape.cledson.com.br`
- Main: `scalescrape.cledson.com.br`, `api.scalescrape.cledson.com.br`, `grafana.scalescrape.cledson.com.br`

RabbitMQ, Postgres e Prometheus ficam internos no Docker. Os Actions executam
testes Python, `npm test`, `npm run typecheck`, `npm run build`, publicam as
imagens, fazem SSH na VPS, atualizam `.env.production`, sobem a stack e rodam
smoke de target, API, Grafana e scraping contra
`http://target-site:4000/protected/items?page=1`.

Secrets esperados no GitHub:

```text
VPS_HOST
VPS_USER
VPS_SSH_KEY
DEVELOPMENT_VPS_APP_DIR
PRODUCTION_VPS_APP_DIR
TWO_CAPTCHA_API_KEY
DEVELOPMENT_TARGET_SITE_PORT
DEVELOPMENT_API_PORT
DEVELOPMENT_GRAFANA_PORT
PRODUCTION_TARGET_SITE_PORT
PRODUCTION_API_PORT
PRODUCTION_GRAFANA_PORT
DEVELOPMENT_POSTGRES_PASSWORD
PRODUCTION_POSTGRES_PASSWORD
DEVELOPMENT_RABBITMQ_PASSWORD
PRODUCTION_RABBITMQ_PASSWORD
DEVELOPMENT_GRAFANA_ADMIN_PASSWORD
PRODUCTION_GRAFANA_ADMIN_PASSWORD
```

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

Sem Docker, e possivel validar as regras puras do worker com o Python local:

```powershell
python -m unittest discover -s tests -v
```

Para validar o target-site Next.js:

```powershell
cd apps\target_site
npm test
npm run typecheck
npm run build
```

No ambiente Codex, foi usado o Python embutido:

```powershell
& "C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```

