import React from "react";

import type { DashboardData, ExtractedItem, JobSummary, PaginatedItems } from "../lib/dashboard-api";

type DashboardPageProps = DashboardData & {
  createdJobs?: string;
};

type PageKey = "fakePage" | "booksPage" | "globoPage";

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

function dashboardHref(key: PageKey, value: number, pages: { fakeItems: PaginatedItems; booksItems: PaginatedItems; globoItems: PaginatedItems }): string {
  const params = new URLSearchParams();
  const next = {
    fakePage: pages.fakeItems.page,
    booksPage: pages.booksItems.page,
    globoPage: pages.globoItems.page,
    [key]: value
  };
  for (const [name, page] of Object.entries(next)) {
    if (page > 1) {
      params.set(name, String(page));
    }
  }
  const query = params.toString();
  return query ? `/dashboard?${query}` : "/dashboard";
}

function TablePager({ pageData, pageKey, pages }: { pageData: PaginatedItems; pageKey: PageKey; pages: { fakeItems: PaginatedItems; booksItems: PaginatedItems; globoItems: PaginatedItems } }) {
  if (pageData.total_pages <= 1) {
    return null;
  }
  const previous = Math.max(1, pageData.page - 1);
  const next = Math.min(pageData.total_pages, pageData.page + 1);

  return (
    <nav className="table-pager" aria-label="Paginacao da tabela">
      <a className={pageData.page === 1 ? "disabled" : ""} href={dashboardHref(pageKey, previous, pages)}>Anterior</a>
      <span>Pagina {pageData.page} de {pageData.total_pages}</span>
      <a className={pageData.page === pageData.total_pages ? "disabled" : ""} href={dashboardHref(pageKey, next, pages)}>Proxima</a>
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

function FakeItemsTable({ pageData, pages }: { pageData: PaginatedItems; pages: { fakeItems: PaginatedItems; booksItems: PaginatedItems; globoItems: PaginatedItems } }) {
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
        <table className="dashboard-table source-table">
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
      <TablePager pageData={pageData} pageKey="fakePage" pages={pages} />
    </section>
  );
}

function BooksItemsTable({ pageData, pages }: { pageData: PaginatedItems; pages: { fakeItems: PaginatedItems; booksItems: PaginatedItems; globoItems: PaginatedItems } }) {
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
        <table className="dashboard-table extracted-table">
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
      <TablePager pageData={pageData} pageKey="booksPage" pages={pages} />
    </section>
  );
}

function GloboItemsTable({ pageData, pages }: { pageData: PaginatedItems; pages: { fakeItems: PaginatedItems; booksItems: PaginatedItems; globoItems: PaginatedItems } }) {
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
        <table className="dashboard-table globo-table">
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
      <TablePager pageData={pageData} pageKey="globoPage" pages={pages} />
    </section>
  );
}

export function DashboardPage({ jobs, items, fakeItems, booksItems, globoItems, apiError, createdJobs }: DashboardPageProps) {
  const successCount = jobs.filter((job) => job.status === "success").length;
  const failedCount = jobs.filter((job) => job.status === "failed" || job.status === "blocked_by_policy").length;
  const latestSuccess = lastSuccess(jobs);
  const pages = { fakeItems, booksItems, globoItems };
  const visibleItems = fakeItems.total + booksItems.total + globoItems.total || items.length;

  return (
    <>
      <section className="list-hero dashboard-hero">
        <span className="eyebrow">painel operacional</span>
        <h1>Dados extraidos pelo ScaleScrape</h1>
        <p>
          Acompanhe jobs, veja registros persistidos no Postgres e dispare consultas imediatas nos tres alvos.
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

        <FakeItemsTable pageData={fakeItems} pages={pages} />
        <BooksItemsTable pageData={booksItems} pages={pages} />
        <GloboItemsTable pageData={globoItems} pages={pages} />
      </main>
    </>
  );
}
