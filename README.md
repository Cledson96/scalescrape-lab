# ScaleScrape Lab

Laboratorio controlado de scraping em escala com Python, RabbitMQ, Playwright,
PostgreSQL, Prometheus, Grafana, target-site em Next.js/TypeScript, anti-bot
simulator, proxy rotation local, login protegido e CAPTCHA configuravel para
ambiente de laboratorio.

O objetivo e mostrar arquitetura de scraping em producao: filas, workers,
controle de concorrencia, retry/backoff, DLQ, circuit breaker, politicas de
seguranca, metricas e observabilidade. Tudo roda contra um target-site local do
proprio projeto.

Para uma explicacao detalhada do fluxo do job, veja
[docs/fluxo-scraping.md](docs/fluxo-scraping.md).

## Arquitetura

```text
Usuario / Swagger
        ↓
FastAPI API
        ↓
PostgreSQL + job_events
        ↓
RabbitMQ
        ↓
Celery Workers
        ↓
Playwright headless
        ↓
Proxy Manager
        ↓
Target Site Fake
        ↓
Login protegido
        ↓
CAPTCHA de laboratorio
        ↓
Anti-Bot Simulator
```

## Stack

- Python + FastAPI para API de orquestracao
- Next.js 16 + TypeScript para target-site fake visual
- Celery + RabbitMQ para filas
- Playwright Python para scraping
- PostgreSQL com SQLAlchemy
- Prometheus + Grafana para monitoramento
- Provider de CAPTCHA plugavel, com mock local por padrao
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
proprietarios.

O portal inteiro exige login fake antes de mostrar qualquer pagina de dados; sem
cookie `lab_auth=ok`, `/`, `/items`, `/external/items` e demais rotas
redirecionam para `/login`. O login valida usuario, senha e CAPTCHA no servidor.
Depois do login, a home (`/`) mostra os cenarios disponiveis e as paginas de
dados preservam os seletores usados pelo Playwright:

- `/items?page=1`: dataset local sintetico, paginado e estavel
- `/login?next=/protected/items?page=1`: login fake com CAPTCHA de laboratorio
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

Para o scraping externo seguro, use a fonte publica Books to Scrape na categoria
Science Fiction:

```json
{
  "source": "books-to-scrape",
  "start_url": "https://books.toscrape.com/catalogue/category/books/science-fiction_16/index.html",
  "mode": "browser",
  "max_pages": 1
}
```

Esse fluxo extrai titulo, preco original em GBP, preco convertido para BRL,
nota, link de detalhe e descricao do livro. A conversao usa a taxa configuravel
`GBP_TO_BRL_RATE`, que por padrao fica em `6.50` para manter a demo
deterministica.

Depois que o job terminar, veja os registros extraidos em:

```text
GET /items
GET /jobs/{job_id}/items
```

Outros cenarios do target controlado:

```text
http://target-site:4000/items?page=1
http://target-site:4000/external/items?page=1
http://target-site:4000/rate-limited/items?page=1
http://target-site:4000/forbidden/items?page=1
http://target-site:4000/unstable/items?page=1
http://target-site:4000/layout-changed/items?page=1
```

## Login, CAPTCHA E Uso Seguro

Por padrao, o projeto usa `MockCaptchaResolverProvider` para desenvolvimento
local. O target-site exige login antes de qualquer pagina do portal; o worker
detecta `#login-form`, preenche `TARGET_SITE_USERNAME` e
`TARGET_SITE_PASSWORD`, passa pela etapa de CAPTCHA configurada no laboratorio e
continua a raspagem dos `.item-card`.

Credenciais demo:

```env
TARGET_SITE_USERNAME=demo
TARGET_SITE_PASSWORD=demo123
```

Variaveis de CAPTCHA usadas pelo target-site:

```text
RECAPTCHA_SITE_KEY
RECAPTCHA_SECRET_KEY
```

No desenvolvimento local, `.env.example` traz chaves de teste do Google para
permitir a validacao da tela sem configurar uma conta real. Em deploy, as chaves
devem vir dos GitHub Secrets.

O worker tambem valida `ALLOWED_CAPTCHA_HOSTS` antes de usar qualquer provider
externo. Este laboratorio deve ser usado apenas contra o target controlado do
proprio projeto ou ambientes explicitamente autorizados.

### Fluxo Resumido

1. `POST /jobs` cria um job no Postgres e publica uma tarefa em `scrape.jobs`.
2. O worker Celery seleciona um proxy logico (`proxy-a`, `proxy-b`, `proxy-c`).
3. O Playwright abre a URL protegida e e redirecionado para `/login`.
4. O worker preenche usuario/senha, passa pelo CAPTCHA do laboratorio e recebe
   os cookies `lab_auth=ok` e `lab_clearance=ok`.
5. A pagina protegida roda o anti-bot local e pode liberar, atrasar, desafiar ou
   bloquear.
6. Com acesso liberado, o worker extrai `.item-card`, `.item-title` e
   `.detail-link`.
7. Os itens sao gravados em `scraped_items`; o job passa para `success`,
   `failed`, `blocked`, `rate_limited` ou `blocked_by_policy`.

Para Books to Scrape, o worker usa o layout `article.product_pod`, abre cada
pagina de detalhe do livro, le `#product_description + p` e grava os campos
normalizados em `raw_data`.

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
- RabbitMQ Management opcional: `rabbit-dev.scalescrape.cledson.com.br` e `rabbit.scalescrape.cledson.com.br`

Postgres, AMQP do RabbitMQ e Prometheus ficam internos no Docker. O painel
RabbitMQ Management pode ser publicado atras do Nginx, preso em `127.0.0.1` nas
portas `11572` (dev) e `11573` (main). Os Actions criam o usuario
`scalescrape_viewer` com tag `monitoring`; a senha e o mesmo valor de
`DEVELOPMENT_RABBITMQ_PASSWORD` ou `PRODUCTION_RABBITMQ_PASSWORD`.

Os Actions executam
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
RECAPTCHA_SITE_KEY
RECAPTCHA_SECRET_KEY
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

Secrets opcionais para trocar as portas padrao do RabbitMQ Management:

```text
DEVELOPMENT_RABBITMQ_MANAGEMENT_PORT
PRODUCTION_RABBITMQ_MANAGEMENT_PORT
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

- demonstrar login protegido e CAPTCHA em target controlado de laboratorio
- simular anti-bot no target-site proprio
- simular proxy rotation em ambiente local
- simular 403, 429, timeout e challenge
- demonstrar arquitetura de scraping em escala

Este projeto nao faz:

- bypass de Cloudflare real
- resolucao de CAPTCHA em sites de terceiros
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

