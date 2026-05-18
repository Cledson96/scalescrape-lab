# Fluxo De Scraping

Este documento descreve como o ScaleScrape Lab funciona na branch atual. A ideia
e facilitar a apresentacao do projeto: a pessoa consegue ver fila, worker,
browser automatizado, login protegido, persistencia, metricas e observabilidade
trabalhando juntos.

## Visao Geral

```text
POST /jobs
  -> Postgres: jobs + job_events
  -> RabbitMQ: fila scrape.jobs
  -> Celery Beat cria jobs periodicos a cada 6 horas
  -> Celery worker
  -> Playwright headless
  -> Target-site Next.js
  -> Login protegido + CAPTCHA de laboratorio
  -> Anti-bot local
  -> Extracao dos cards
  -> Postgres: scraped_items
  -> Prometheus/Grafana/RabbitMQ UI
```

## 1. Criacao Do Job

A API FastAPI recebe `POST /jobs` com uma URL inicial:

```json
{
  "source": "fake-target",
  "start_url": "http://target-site:4000/protected/items?page=1",
  "mode": "browser",
  "max_pages": 1
}
```

Ela valida a fonte, cria um registro em `jobs`, grava um evento `job_created` e
publica a tarefa `app.tasks.run_scrape_job` na fila `scrape.jobs`.

Tambem existe o fluxo automatico: o servico `scheduler`, rodando Celery Beat,
dispara `app.tasks.enqueue_scheduled_scrape_jobs` a cada 21600 segundos
(6 horas). Essa tarefa cria tres jobs:

- target protegido do laboratorio;
- Books to Scrape na categoria Science Fiction;
- Globo Home para noticias publicas da home.

Para demonstrar um segundo scraping externo seguro, use a fonte
`books-to-scrape`:

```json
{
  "source": "books-to-scrape",
  "start_url": "https://books.toscrape.com/catalogue/category/books/science-fiction_16/index.html",
  "mode": "browser",
  "max_pages": 1
}
```

Para demonstrar scraping de noticias publicas com imagem local, use:

```json
{
  "source": "globo-home",
  "start_url": "https://www.globo.com/",
  "mode": "browser",
  "max_pages": 1
}
```

## 2. Fila E Worker

O RabbitMQ segura o trabalho ate o Celery worker consumir a mensagem. O worker:

- carrega o job no Postgres;
- valida hosts permitidos por policy;
- seleciona um proxy logico local;
- marca o job como `running`;
- registra o evento `proxy_selected`.

Os proxies sao simulados com o header `X-Lab-Proxy-Id`, usando `proxy-a`,
`proxy-b` e `proxy-c`.

## 3. Browser E Login

O worker abre Chromium headless via Playwright. Ao acessar
`/protected/items?page=1`, o target-site redireciona para `/login` quando nao ha
cookie `lab_auth=ok`.

Quando encontra `#login-form`, o worker preenche:

- `TARGET_SITE_USERNAME`
- `TARGET_SITE_PASSWORD`

Depois passa pela etapa de CAPTCHA configurada para o laboratorio. Em dev local,
o provider mock permite testar o fluxo sem custo externo. Em ambientes
controlados, qualquer provider externo deve respeitar `ALLOWED_CAPTCHA_HOSTS` e
o limite `MAX_CAPTCHA_SOLVES_PER_RUN`.

Com login valido, o target-site grava:

- `lab_auth=ok`
- `lab_clearance=ok`

## 4. Anti-Bot Local

Depois do login, `/protected/items` executa o simulador anti-bot. Ele considera:

- session id;
- proxy logico;
- user-agent;
- cookie de clearance.

As acoes simuladas sao:

- liberar a pagina;
- atrasar resposta;
- mostrar challenge local;
- retornar bloqueio.

Isso permite demonstrar tratamento de `403`, `429`, delay, retry, cooldown e
quebra de layout sem tocar em sites reais.

## 5. Extracao

Quando a pagina e liberada, o worker procura `.item-card`. Para cada card, ele
extrai:

- `data-item-id`;
- texto de `.item-title`;
- `href` de `.detail-link`.

Se houver `.next-page`, o worker segue a paginacao ate `max_pages`.

No Books to Scrape, o worker usa outro adaptador:

- lista os livros em `article.product_pod`;
- captura titulo, preco em GBP, nota e link;
- abre a pagina de detalhe do livro;
- extrai a descricao em `#product_description + p`;
- grava tambem o preco convertido para BRL usando `GBP_TO_BRL_RATE`.

Na Globo, o worker usa um adaptador dedicado:

- lista links publicos `.post__link` na home;
- identifica categoria pelo bloco visual `data-tracking-action`;
- abre paginas `.ghtml` para ler `og:title`, `og:description` e `og:image`;
- baixa imagens permitidas de `*.glbimg.com` para `MEDIA_ROOT/globo`;
- grava `image_public_path` para que a API sirva a thumbnail em `/media`.

## 6. Persistencia E Status

Ao final, os dados vao para `scraped_items`. O campo `created_at` e exposto pela
API tambem como `extracted_at`, deixando claro quando cada item foi coletado.
O mesmo horario e gravado em `raw_data.extracted_at`.

O job recebe um destes status:

- `success`: terminou e encontrou itens;
- `failed`: erro tecnico ou layout inesperado;
- `blocked`: bloqueio `403`;
- `rate_limited`: bloqueio `429`;
- `blocked_by_policy`: URL ou host fora da whitelist.

Eventos importantes ficam em `job_events`, o que ajuda a explicar a historia do
job durante a demo.

Os dados coletados podem ser vistos pela API:

```text
GET /items
GET /items/page?source=globo-home&page=1&page_size=10
GET /jobs/{job_id}/items
```

Tambem ha uma vitrine visual em `/dashboard` no target-site. Ela consulta a API
server-side por `SCALESCRAPE_API_URL`, mostra `public_url`/`public_detail_url`
para trocar `http://target-site:4000` pelo dominio publico do ambiente, e possui
botoes para criar jobs imediatos dos tres scrapers. O dashboard mostra tabelas
paginadas separadas para fake-target, Books to Scrape e Globo; as imagens da
Globo sao servidas pela API com `PUBLIC_API_URL`.

O target-site tambem tem uma fonte dinamica propria: `/external/items` busca a
API real RandomUser, normaliza os dados sem expor e-mail/telefone/documento, usa
cache de 6 horas e fallback local se a API externa ficar indisponivel.

## 7. Observabilidade

Durante a execucao, voce consegue mostrar:

- API Swagger: `http://localhost:8000/docs`;
- lista de jobs: `GET /jobs`;
- RabbitMQ Management: `http://localhost:15672`;
- Prometheus: `http://localhost:9090`;
- Grafana: `http://localhost:3000`.

Na VPS, as portas publicas ficam atras do Nginx, enquanto Postgres, Prometheus e
AMQP ficam internos.

## Nota De Escopo

O ScaleScrape Lab foi feito para demonstrar arquitetura de scraping em ambiente
proprio e controlado. Ele nao deve ser usado para burlar CAPTCHA, Cloudflare,
rate limit ou controles anti-bot de sites de terceiros.
