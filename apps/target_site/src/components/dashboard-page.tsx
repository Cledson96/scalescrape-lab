import Link from "next/link";

import { getPublicApiBaseUrl, type DashboardData, type ExtractedItem, type JobSummary, type PaginatedItems } from "../lib/dashboard-api";

type DashboardPageProps = DashboardData & {
  activeTab?: DashboardTab;
  createdJobs?: string;
};

type DashboardTab = "fake" | "books" | "globo" | "betano";
type PageKey = "fakePage" | "booksPage" | "globoPage" | "betanoPage";
type DashboardPages = {
  fakeItems: PaginatedItems;
  booksItems: PaginatedItems;
  globoItems: PaginatedItems;
  betanoItems: PaginatedItems;
};

const sourceTablesAnchor = "dados-extraidos";

const dashboardTabs: Array<{ key: DashboardTab; label: string; description: string }> = [
  { key: "fake", label: "Site fake", description: "Sessao e anti-bot" },
  { key: "books", label: "Books", description: "Preco e nota" },
  { key: "globo", label: "Globo", description: "Noticias e imagem" },
  { key: "betano", label: "Betano", description: "Odds reais" }
];

const casePillars = [
  {
    title: "Desenvolvimento e performance",
    body: "Pipeline com API, jobs persistidos, retry, timeout, Playwright e workers paralelos para simular alta volumetria.",
    tags: ["Python", "Next.js", "Playwright"]
  },
  {
    title: "Infraestrutura e rede",
    body: "Controle de sessao, cookies, rate limit, proxy, captcha em laboratorio proprio e politicas de whitelist para execucao segura.",
    tags: ["HTTP", "cookies", "proxy policy"]
  },
  {
    title: "Operacao distribuida",
    body: "RabbitMQ, Postgres, Prometheus, Grafana, Docker e deploy automatizado para mostrar observabilidade de ponta a ponta.",
    tags: ["RabbitMQ", "Postgres", "Grafana"]
  }
];

const architectureSteps = [
  "Target Next.js",
  "API FastAPI",
  "RabbitMQ",
  "Workers Playwright",
  "Postgres",
  "Prometheus + Grafana",
  "Docker + GitHub Actions"
];

const scrapeActions = [
  { source: "fake-target", label: "Consultar fake agora", detail: "Login, captcha e sessao" },
  { source: "books-to-scrape", label: "Consultar Books agora", detail: "Preco, nota e descricao" },
  { source: "globo-home", label: "Consultar Globo agora", detail: "Noticias e imagens" },
  { source: "betano-football", label: "Consultar Betano agora", detail: "Odds de futebol" },
  { source: "all", label: "Consultar todos agora", detail: "Executa as quatro fontes" }
] as const;

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo"
  }).format(new Date(value));
}

function readNested(rawData: Record<string, unknown>, key: string): unknown {
  return key.split(".").reduce<unknown>((current, part) => {
    if (current && typeof current === "object" && part in current) {
      return (current as Record<string, unknown>)[part];
    }
    return undefined;
  }, rawData);
}

function textValue(value: unknown, fallback = "-"): string {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  return String(value);
}

function statusClass(status: string): string {
  if (status === "success") {
    return "green";
  }
  if (status === "failed" || status === "blocked" || status === "blocked_by_policy") {
    return "red";
  }
  if (status === "running" || status === "pending") {
    return "amber";
  }
  return "blue";
}

function itemPrice(item: ExtractedItem): string {
  const original = readNested(item.raw_data, "price.formatted");
  const converted = readNested(item.raw_data, "price.brl_formatted");
  if (original && converted) {
    return `${original} / ${converted}`;
  }
  return "-";
}

function itemRating(item: ExtractedItem): string {
  const label = readNested(item.raw_data, "rating.label");
  const value = readNested(item.raw_data, "rating.value");
  if (label && value) {
    return `${label} (${value}/5)`;
  }
  return "-";
}

function rawNumber(value: unknown): string {
  if (typeof value === "number") {
    return value.toFixed(2);
  }
  return textValue(value);
}

function shortDescription(item: ExtractedItem, fallback = "-"): string {
  const description = textValue(item.raw_data.description, "");
  if (!description) {
    return fallback;
  }
  return description.length > 170 ? `${description.slice(0, 170)}...` : description;
}

function lastSuccess(jobs: JobSummary[]): JobSummary | undefined {
  return jobs.find((job) => job.status === "success");
}

function dashboardHref(key: PageKey, value: number, pages: DashboardPages, activeTab: DashboardTab): string {
  const params = new URLSearchParams();
  const next = {
    fakePage: pages.fakeItems.page,
    booksPage: pages.booksItems.page,
    globoPage: pages.globoItems.page,
    betanoPage: pages.betanoItems.page,
    [key]: value
  };
  params.set("tab", activeTab);
  params.set(key, String(value));
  for (const [name, page] of Object.entries(next)) {
    if (page > 1) {
      params.set(name, String(page));
    }
  }
  return `/dashboard?${params.toString()}`;
}

function tabHref(tab: DashboardTab, pages: DashboardPages): string {
  const params = new URLSearchParams({ tab });
  if (pages.fakeItems.page > 1) {
    params.set("fakePage", String(pages.fakeItems.page));
  }
  if (pages.booksItems.page > 1) {
    params.set("booksPage", String(pages.booksItems.page));
  }
  if (pages.globoItems.page > 1) {
    params.set("globoPage", String(pages.globoItems.page));
  }
  if (pages.betanoItems.page > 1) {
    params.set("betanoPage", String(pages.betanoItems.page));
  }
  return `/dashboard?${params.toString()}`;
}

function TablePager({ pageData, pageKey, pages, activeTab }: { pageData: PaginatedItems; pageKey: PageKey; pages: DashboardPages; activeTab: DashboardTab }) {
  if (pageData.total_pages <= 1) {
    return null;
  }
  const previous = Math.max(1, pageData.page - 1);
  const next = Math.min(pageData.total_pages, pageData.page + 1);

  return (
    <nav className="table-pager" aria-label="Paginacao da tabela">
      <Link className={pageData.page === 1 ? "disabled" : ""} href={dashboardHref(pageKey, previous, pages, activeTab)} scroll={false}>Anterior</Link>
      <span>Pagina {pageData.page} de {pageData.total_pages}</span>
      <Link className={pageData.page === pageData.total_pages ? "disabled" : ""} href={dashboardHref(pageKey, next, pages, activeTab)} scroll={false}>Proxima</Link>
    </nav>
  );
}

function EmptyRow({ colSpan }: { colSpan: number }) {
  return (
    <tr>
      <td colSpan={colSpan} className="empty-cell">Nenhum registro extraido ainda.</td>
    </tr>
  );
}

function SourceTabs({ activeTab, pages }: { activeTab: DashboardTab; pages: DashboardPages }) {
  const counts: Record<DashboardTab, number> = {
    fake: pages.fakeItems.total,
    books: pages.booksItems.total,
    globo: pages.globoItems.total,
    betano: pages.betanoItems.total
  };

  return (
    <nav className="dashboard-tabs" aria-label="Selecionar tabela">
      {dashboardTabs.map((tab) => (
        <Link
          key={tab.key}
          className={`dashboard-tab ${activeTab === tab.key ? "active" : ""}`}
          href={tabHref(tab.key, pages)}
          scroll={false}
        >
          <strong>{tab.label}</strong>
          <span>{tab.description}</span>
          <em>{counts[tab.key]} itens</em>
        </Link>
      ))}
    </nav>
  );
}

function FakeItemsTable({ pageData, pages, activeTab }: { pageData: PaginatedItems; pages: DashboardPages; activeTab: DashboardTab }) {
  return (
    <section className="dashboard-section table-section">
      <div className="section-head">
        <div>
          <h2>Site fake protegido</h2>
          <p>Registros coletados apos login, sessao e desafio anti-bot do laboratorio.</p>
        </div>
        <span className="table-count">{pageData.total} itens</span>
      </div>
      <div className="table-wrap">
        <table className="dashboard-table source-table rich-table">
          <caption className="table-caption">Extracao protegida com login, cookie e desafio controlado</caption>
          <thead>
            <tr>
              <th>Titulo</th>
              <th>Categoria</th>
              <th>Origem</th>
              <th>Job</th>
              <th>Extraido em</th>
            </tr>
          </thead>
          <tbody>
            {pageData.items.length === 0 ? <EmptyRow colSpan={5} /> : null}
            {pageData.items.map((item) => (
              <tr key={item.id}>
                <td className="primary-cell">
                  <a className="table-main-link" href={item.public_detail_url ?? item.detail_url}>{item.title}</a>
                  <span className="table-subtle">{item.external_id}</span>
                </td>
                <td><span className="tag blue">{textValue(item.raw_data.category, "target protegido")}</span></td>
                <td><span className="source-chip">fake-target</span></td>
                <td><span className="job-pill">#{item.job_id}</span></td>
                <td className="time-cell">{formatDate(item.extracted_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TablePager pageData={pageData} pageKey="fakePage" pages={pages} activeTab={activeTab} />
    </section>
  );
}

function BooksItemsTable({ pageData, pages, activeTab }: { pageData: PaginatedItems; pages: DashboardPages; activeTab: DashboardTab }) {
  return (
    <section className="dashboard-section table-section">
      <div className="section-head">
        <div>
          <h2>Books to Scrape</h2>
          <p>Livros de science-fiction com preco original, conversao para real, nota e descricao.</p>
        </div>
        <span className="table-count">{pageData.total} itens</span>
      </div>
      <div className="table-wrap">
        <table className="dashboard-table extracted-table rich-table">
          <caption className="table-caption">Catalogo externo normalizado com preco convertido e avaliacao</caption>
          <thead>
            <tr>
              <th>Titulo</th>
              <th>Preco</th>
              <th>Nota</th>
              <th>Descricao</th>
              <th>Extraido em</th>
            </tr>
          </thead>
          <tbody>
            {pageData.items.length === 0 ? <EmptyRow colSpan={5} /> : null}
            {pageData.items.map((item) => (
              <tr key={item.id}>
                <td className="primary-cell">
                  <a className="table-main-link" href={item.public_detail_url ?? item.detail_url}>{item.title}</a>
                  <span className="table-subtle">job #{item.job_id} - {item.external_id}</span>
                </td>
                <td><span className="money-pill">{itemPrice(item)}</span></td>
                <td><span className="rating-pill">{itemRating(item)}</span></td>
                <td className="description-cell">{shortDescription(item)}</td>
                <td className="time-cell">{formatDate(item.extracted_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TablePager pageData={pageData} pageKey="booksPage" pages={pages} activeTab={activeTab} />
    </section>
  );
}

function GloboItemsTable({ pageData, pages, activeTab }: { pageData: PaginatedItems; pages: DashboardPages; activeTab: DashboardTab }) {
  return (
    <section className="dashboard-section table-section">
      <div className="section-head">
        <div>
          <h2>Globo noticias</h2>
          <p>Noticias publicas da home agrupadas por categoria, com imagem salva no storage local.</p>
        </div>
        <span className="table-count">{pageData.total} itens</span>
      </div>
      <div className="table-wrap">
        <table className="dashboard-table globo-table rich-table">
          <caption className="table-caption">Noticias publicas com categoria, thumbnail e link original preservado</caption>
          <thead>
            <tr>
              <th>Imagem</th>
              <th>Categoria</th>
              <th>Titulo e detalhe</th>
              <th>Link</th>
              <th>Extraido em</th>
            </tr>
          </thead>
          <tbody>
            {pageData.items.length === 0 ? <EmptyRow colSpan={5} /> : null}
            {pageData.items.map((item) => (
              <tr key={item.id}>
                <td>
                  {item.public_image_url ? (
                    <img className="news-thumb" src={item.public_image_url} alt="" />
                  ) : (
                    <span className="thumb-placeholder">sem imagem</span>
                  )}
                </td>
                <td><span className="tag blue">{textValue(item.raw_data.category, "noticia")}</span></td>
                <td className="primary-cell description-cell">
                  <a className="table-main-link" href={item.public_detail_url ?? item.detail_url}>{item.title}</a>
                  <span className="table-subtle">{shortDescription(item, "Resumo nao disponivel")}</span>
                </td>
                <td><a className="table-link" href={item.public_detail_url ?? item.detail_url}>Abrir noticia</a></td>
                <td className="time-cell">{formatDate(item.extracted_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TablePager pageData={pageData} pageKey="globoPage" pages={pages} activeTab={activeTab} />
    </section>
  );
}

function BetanoItemsTable({ pageData, pages, activeTab }: { pageData: PaginatedItems; pages: DashboardPages; activeTab: DashboardTab }) {
  return (
    <section className="dashboard-section table-section active-source-section">
      <div className="section-head">
        <div>
          <h2>Betano futebol</h2>
          <p>Odds reais coletadas pelo worker na categoria futebol, com campeonato, jogo e mercado.</p>
        </div>
        <span className="table-count">{pageData.total} itens</span>
      </div>
      <div className="table-wrap">
        <table className="dashboard-table betano-table rich-table">
          <caption className="table-caption">Mercados reais persistidos pelo worker com odds em formato auditavel</caption>
          <thead>
            <tr>
              <th>Campeonato</th>
              <th>Jogo</th>
              <th>Data/hora</th>
              <th>Mercado</th>
              <th>Odd 1</th>
              <th>Odd X</th>
              <th>Odd 2</th>
              <th>Extraido em</th>
            </tr>
          </thead>
          <tbody>
            {pageData.items.length === 0 ? <EmptyRow colSpan={8} /> : null}
            {pageData.items.map((item) => {
              const homeTeam = textValue(item.raw_data.home_team, item.title);
              const awayTeam = textValue(item.raw_data.away_team, "");
              const matchName = awayTeam ? `${homeTeam} x ${awayTeam}` : homeTeam;
              const dateTime = [textValue(item.raw_data.match_date, ""), textValue(item.raw_data.match_time, "")]
                .filter(Boolean)
                .join(" ");
              return (
                <tr key={item.id}>
                  <td><span className="tag blue">{textValue(item.raw_data.championship, "Futebol")}</span></td>
                  <td className="primary-cell match-cell">
                    <a className="table-main-link" href={item.public_detail_url ?? item.detail_url}>{matchName}</a>
                    <span className="table-subtle">job #{item.job_id}</span>
                  </td>
                  <td className="time-cell">{dateTime || "-"}</td>
                  <td>{textValue(item.raw_data.market_type, "Resultado da partida")}</td>
                  <td className="numeric-cell"><strong className="odd-pill">{rawNumber(readNested(item.raw_data, "odds.home_raw") ?? readNested(item.raw_data, "odds.home"))}</strong></td>
                  <td className="numeric-cell"><strong className="odd-pill">{rawNumber(readNested(item.raw_data, "odds.draw_raw") ?? readNested(item.raw_data, "odds.draw"))}</strong></td>
                  <td className="numeric-cell"><strong className="odd-pill">{rawNumber(readNested(item.raw_data, "odds.away_raw") ?? readNested(item.raw_data, "odds.away"))}</strong></td>
                  <td className="time-cell">{formatDate(textValue(item.raw_data.extracted_at, item.extracted_at))}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <TablePager pageData={pageData} pageKey="betanoPage" pages={pages} activeTab={activeTab} />
    </section>
  );
}

function ActiveSourceTable({ activeTab, pages }: { activeTab: DashboardTab; pages: DashboardPages }) {
  if (activeTab === "books") {
    return <BooksItemsTable pageData={pages.booksItems} pages={pages} activeTab={activeTab} />;
  }
  if (activeTab === "globo") {
    return <GloboItemsTable pageData={pages.globoItems} pages={pages} activeTab={activeTab} />;
  }
  if (activeTab === "betano") {
    return <BetanoItemsTable pageData={pages.betanoItems} pages={pages} activeTab={activeTab} />;
  }
  return <FakeItemsTable pageData={pages.fakeItems} pages={pages} activeTab={activeTab} />;
}

export function DashboardPage({ activeTab = "fake", jobs, items, fakeItems, booksItems, globoItems, betanoItems, apiError, createdJobs }: DashboardPageProps) {
  const successCount = jobs.filter((job) => job.status === "success").length;
  const failedCount = jobs.filter((job) => job.status === "failed" || job.status === "blocked_by_policy").length;
  const latestSuccess = lastSuccess(jobs);
  const pages = { fakeItems, booksItems, globoItems, betanoItems };
  const visibleItems = fakeItems.total + booksItems.total + globoItems.total + betanoItems.total || items.length;
  const successRate = jobs.length > 0 ? `${Math.round((successCount / jobs.length) * 100)}%` : "0%";
  const swaggerUrl = `${getPublicApiBaseUrl()}/docs`;

  return (
    <>
      <section className="dashboard-hero dashboard-hero-compact">
        <div className="case-hero-copy">
          <span className="eyebrow">Case tecnico autoral para vaga Procob</span>
          <h1>Scraping distribuido em escala</h1>
          <p>
            Centro operacional para disparar coletas, acompanhar jobs e validar dados persistidos por fonte, com
            foco em rede, anti-bot, filas e observabilidade.
          </p>
          <div className="case-badge-row" aria-label="Competencias demonstradas">
            <span>HTTP, headers e cookies</span>
            <span>Retry, timeout e throughput</span>
            <span>Workers e Docker na VPS</span>
          </div>
        </div>
        <aside className="case-snapshot compact-snapshot" aria-label="Resumo da stack">
          <span>Stack e arquitetura</span>
          <strong>Pipeline pronto para demo</strong>
          <ul>
            <li>RabbitMQ para distribuir jobs</li>
            <li>Workers Playwright para paginas dinamicas</li>
            <li>Docker + GitHub Actions para deploy dev/main</li>
          </ul>
        </aside>
      </section>

      <main className="content dashboard-content">
        {apiError ? <div className="dashboard-alert">API indisponivel: {apiError}</div> : null}
        {createdJobs ? <div className="dashboard-alert success">Jobs criados agora: {createdJobs}</div> : null}

        <section className="dashboard-control-panel" aria-label="Criar scraping agora">
          <div className="control-copy">
            <span className="eyebrow">operacao ao vivo</span>
            <h2>Dispare coletas agora</h2>
            <p>
              Cada botao cria jobs na API, envia para a fila e alimenta as tabelas abaixo assim que o worker persiste os dados.
            </p>
          </div>
          <div className="dashboard-actions">
            {scrapeActions.map((action) => (
              <form action="/dashboard/run" method="post" key={action.source}>
                <input type="hidden" name="source" value={action.source} />
                <button type="submit">
                  <strong>{action.label}</strong>
                  <span>{action.detail}</span>
                </button>
              </form>
            ))}
            <a className="secondary-dashboard-action" href="/dashboard">
              <strong>Atualizar painel</strong>
              <span>Recarregar status</span>
            </a>
            <a className="secondary-dashboard-action" href={swaggerUrl} target="_blank" rel="noreferrer">
              <strong>Abrir Swagger da API</strong>
              <span>Ver rotas, exemplos e schemas detalhados</span>
            </a>
          </div>
        </section>

        <section className="dashboard-metrics" aria-label="Resumo do scraping">
          <div className="dashboard-metric"><strong>{jobs.length}</strong><span>jobs recentes</span></div>
          <div className="dashboard-metric"><strong>{visibleItems}</strong><span>itens persistidos</span></div>
          <div className="dashboard-metric"><strong>4</strong><span>Fontes ativas</span></div>
          <div className="dashboard-metric"><strong>6h</strong><span>Scheduler 6h</span></div>
          <div className="dashboard-metric"><strong>{successCount}</strong><span>jobs com sucesso</span></div>
          <div className="dashboard-metric"><strong>{successRate}</strong><span>taxa recente</span></div>
          <div className="dashboard-metric"><strong>{failedCount}</strong><span>falhas visiveis</span></div>
        </section>

        <section id={sourceTablesAnchor} className="source-table-shell" aria-label="Dados extraidos por fonte">
          <div className="section-head">
            <div>
              <span className="section-kicker">resultado do scraping</span>
              <h2>Dados extraidos por fonte</h2>
              <p>Troque a fonte sem perder o contexto: a pagina volta direto para as tabelas e a fonte ativa.</p>
            </div>
            <span className="table-count">{visibleItems} itens</span>
          </div>
          <SourceTabs activeTab={activeTab} pages={pages} />
          <ActiveSourceTable activeTab={activeTab} pages={pages} />
        </section>

        <section className="dashboard-section jobs-section">
          <div className="section-head">
            <div>
              <h2>Jobs recentes</h2>
              <p>{latestSuccess ? `Ultimo sucesso em ${formatDate(latestSuccess.created_at)}` : "Aguardando primeiro sucesso."}</p>
            </div>
          </div>
          <div className="table-wrap">
            <table className="dashboard-table jobs-table rich-table">
              <caption className="table-caption">Historico operacional usado para auditar execucoes e falhas recentes</caption>
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Status</th>
                  <th>Itens</th>
                  <th>Alvo publico</th>
                  <th>Criado em</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 ? <EmptyRow colSpan={5} /> : null}
                {jobs.slice(0, 12).map((job) => (
                  <tr key={job.id}>
                    <td><span className="job-pill">#{job.id}</span></td>
                    <td><span className={`tag ${statusClass(job.status)}`}>{job.status}</span></td>
                    <td><strong className="table-number">{job.items_found}</strong></td>
                    <td className="url-cell">
                      <a className="table-link" href={job.public_url ?? job.start_url}>{job.public_url ?? job.start_url}</a>
                    </td>
                    <td className="time-cell">{formatDate(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="case-brief" aria-label="Como este case conversa com a vaga">
          <div className="section-head">
            <div>
              <h2>Case criado para demonstrar fit tecnico</h2>
              <p>O foco e mostrar investigacao, escala, rede, automacao e operacao, nao apenas uma tela bonita.</p>
            </div>
          </div>
          <div className="case-brief-grid">
            {casePillars.map((pillar) => (
              <article className="case-pillar" key={pillar.title}>
                <h3>{pillar.title}</h3>
                <p>{pillar.body}</p>
                <div className="tag-row">
                  {pillar.tags.map((tag) => <span className="tag blue" key={tag}>{tag}</span>)}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="architecture-strip" aria-label="Arquitetura do scraping distribuido">
          {architectureSteps.map((step, index) => (
            <div className="architecture-step" key={step}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </section>
      </main>
    </>
  );
}
