import React from "react";

import type { DashboardData, ExtractedItem, JobSummary, PaginatedItems } from "../lib/dashboard-api";

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

const dashboardTabs: Array<{ key: DashboardTab; label: string; description: string }> = [
  { key: "fake", label: "Site fake", description: "Login, sessao e anti-bot local" },
  { key: "books", label: "Books", description: "Preco, nota e descricao" },
  { key: "globo", label: "Globo", description: "Noticias e imagem local" },
  { key: "betano", label: "Betano", description: "Odds reais do scraper" }
];

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
      <a className={pageData.page === 1 ? "disabled" : ""} href={dashboardHref(pageKey, previous, pages, activeTab)}>Anterior</a>
      <span>Pagina {pageData.page} de {pageData.total_pages}</span>
      <a className={pageData.page === pageData.total_pages ? "disabled" : ""} href={dashboardHref(pageKey, next, pages, activeTab)}>Proxima</a>
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
        <a
          key={tab.key}
          className={`dashboard-tab ${activeTab === tab.key ? "active" : ""}`}
          href={tabHref(tab.key, pages)}
        >
          <strong>{tab.label}</strong>
          <span>{tab.description}</span>
          <em>{counts[tab.key]} itens</em>
        </a>
      ))}
    </nav>
  );
}

function FakeItemsTable({ pageData, pages, activeTab }: { pageData: PaginatedItems; pages: DashboardPages; activeTab: DashboardTab }) {
  return (
    <section className="dashboard-section">
      <div className="section-head">
        <div>
          <h2>Site fake protegido</h2>
          <p>Registros coletados apos login, sessao e desafio anti-bot do laboratorio.</p>
        </div>
        <span className="table-count">{pageData.total} itens</span>
      </div>
      <div className="table-wrap">
        <table className="dashboard-table source-table rich-table">
          <thead>
            <tr>
              <th>Titulo</th>
              <th>Categoria</th>
              <th>Detalhe</th>
              <th>Job</th>
              <th>Extraido em</th>
            </tr>
          </thead>
          <tbody>
            {pageData.items.length === 0 ? <EmptyRow colSpan={5} /> : null}
            {pageData.items.map((item) => (
              <tr key={item.id}>
                <td>{item.title}</td>
                <td>{textValue(item.raw_data.category, "target protegido")}</td>
                <td><a href={item.public_detail_url ?? item.detail_url}>Abrir detalhe</a></td>
                <td>#{item.job_id}</td>
                <td>{formatDate(item.extracted_at)}</td>
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
    <section className="dashboard-section">
      <div className="section-head">
        <div>
          <h2>Books to Scrape</h2>
          <p>Livros de science-fiction com preco original, conversao para real, nota e descricao.</p>
        </div>
        <span className="table-count">{pageData.total} itens</span>
      </div>
      <div className="table-wrap">
        <table className="dashboard-table extracted-table rich-table">
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
                <td>
                  <a href={item.public_detail_url ?? item.detail_url}>{item.title}</a>
                  <span className="table-subtle">job #{item.job_id}</span>
                </td>
                <td>{itemPrice(item)}</td>
                <td>{itemRating(item)}</td>
                <td>{shortDescription(item)}</td>
                <td>{formatDate(item.extracted_at)}</td>
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
    <section className="dashboard-section">
      <div className="section-head">
        <div>
          <h2>Globo noticias</h2>
          <p>Noticias publicas da home agrupadas por categoria, com imagem salva no storage local.</p>
        </div>
        <span className="table-count">{pageData.total} itens</span>
      </div>
      <div className="table-wrap">
        <table className="dashboard-table globo-table rich-table">
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
                <td>
                  <a href={item.public_detail_url ?? item.detail_url}>{item.title}</a>
                  <span className="table-subtle">{shortDescription(item, "Resumo nao disponivel")}</span>
                </td>
                <td><a href={item.public_detail_url ?? item.detail_url}>Abrir noticia</a></td>
                <td>{formatDate(item.extracted_at)}</td>
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
    <section className="dashboard-section active-source-section">
      <div className="section-head">
        <div>
          <h2>Betano futebol</h2>
          <p>Odds reais coletadas pelo worker na categoria futebol, com campeonato, jogo e mercado.</p>
        </div>
        <span className="table-count">{pageData.total} itens</span>
      </div>
      <div className="table-wrap">
        <table className="dashboard-table betano-table rich-table">
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
                  <td>
                    <a href={item.public_detail_url ?? item.detail_url}>{matchName}</a>
                    <span className="table-subtle">job #{item.job_id}</span>
                  </td>
                  <td>{dateTime || "-"}</td>
                  <td>{textValue(item.raw_data.market_type, "Resultado da partida")}</td>
                  <td><strong className="odd-pill">{rawNumber(readNested(item.raw_data, "odds.home_raw") ?? readNested(item.raw_data, "odds.home"))}</strong></td>
                  <td><strong className="odd-pill">{rawNumber(readNested(item.raw_data, "odds.draw_raw") ?? readNested(item.raw_data, "odds.draw"))}</strong></td>
                  <td><strong className="odd-pill">{rawNumber(readNested(item.raw_data, "odds.away_raw") ?? readNested(item.raw_data, "odds.away"))}</strong></td>
                  <td>{formatDate(textValue(item.raw_data.extracted_at, item.extracted_at))}</td>
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

  return (
    <>
      <section className="list-hero dashboard-hero">
        <span className="eyebrow">painel operacional</span>
        <h1>Dados extraidos pelo ScaleScrape</h1>
        <p>
          Acompanhe jobs, veja registros persistidos no Postgres e dispare consultas imediatas nos quatro alvos.
        </p>
      </section>

      <main className="content dashboard-content">
        {apiError ? <div className="dashboard-alert">API indisponivel: {apiError}</div> : null}
        {createdJobs ? <div className="dashboard-alert success">Jobs criados agora: {createdJobs}</div> : null}

        <section className="dashboard-actions" aria-label="Criar scraping agora">
          <form action="/dashboard/run" method="post">
            <input type="hidden" name="source" value="fake-target" />
            <button type="submit">Consultar fake agora</button>
          </form>
          <form action="/dashboard/run" method="post">
            <input type="hidden" name="source" value="books-to-scrape" />
            <button type="submit">Consultar Books agora</button>
          </form>
          <form action="/dashboard/run" method="post">
            <input type="hidden" name="source" value="globo-home" />
            <button type="submit">Consultar Globo agora</button>
          </form>
          <form action="/dashboard/run" method="post">
            <input type="hidden" name="source" value="betano-football" />
            <button type="submit">Consultar Betano agora</button>
          </form>
          <form action="/dashboard/run" method="post">
            <input type="hidden" name="source" value="all" />
            <button type="submit">Consultar todos agora</button>
          </form>
          <a className="secondary-dashboard-action" href="/dashboard">Atualizar painel</a>
        </section>

        <section className="dashboard-metrics" aria-label="Resumo do scraping">
          <div className="dashboard-metric"><strong>{jobs.length}</strong><span>jobs recentes</span></div>
          <div className="dashboard-metric"><strong>{visibleItems}</strong><span>itens persistidos</span></div>
          <div className="dashboard-metric"><strong>{successCount}</strong><span>jobs com sucesso</span></div>
          <div className="dashboard-metric"><strong>{failedCount}</strong><span>falhas visiveis</span></div>
        </section>

        <section className="dashboard-section">
          <div className="section-head">
            <div>
              <h2>Jobs recentes</h2>
              <p>{latestSuccess ? `Ultimo sucesso em ${formatDate(latestSuccess.created_at)}` : "Aguardando primeiro sucesso."}</p>
            </div>
          </div>
          <div className="table-wrap">
            <table className="dashboard-table">
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
                {jobs.slice(0, 12).map((job) => (
                  <tr key={job.id}>
                    <td>#{job.id}</td>
                    <td><span className={`tag ${statusClass(job.status)}`}>{job.status}</span></td>
                    <td>{job.items_found}</td>
                    <td>
                      <a href={job.public_url ?? job.start_url}>{job.public_url ?? job.start_url}</a>
                    </td>
                    <td>{formatDate(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <SourceTabs activeTab={activeTab} pages={pages} />
        <ActiveSourceTable activeTab={activeTab} pages={pages} />
      </main>
    </>
  );
}
