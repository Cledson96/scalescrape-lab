import React from "react";

import type { DashboardData, ExtractedItem, JobSummary } from "../lib/dashboard-api";

type DashboardPageProps = DashboardData & {
  createdJobs?: string;
};

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

function itemSource(item: ExtractedItem): string {
  return textValue(item.raw_data.source, item.detail_url.includes("books.toscrape.com") ? "books-to-scrape" : "fake-target");
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

function shortDescription(item: ExtractedItem): string {
  const description = textValue(item.raw_data.description, "");
  if (!description) {
    return textValue(item.raw_data.category, "registro do target protegido");
  }
  return description.length > 150 ? `${description.slice(0, 150)}...` : description;
}

function lastSuccess(jobs: JobSummary[]): JobSummary | undefined {
  return jobs.find((job) => job.status === "success");
}

export function DashboardPage({ jobs, items, apiError, createdJobs }: DashboardPageProps) {
  const successCount = jobs.filter((job) => job.status === "success").length;
  const failedCount = jobs.filter((job) => job.status === "failed" || job.status === "blocked_by_policy").length;
  const latestSuccess = lastSuccess(jobs);

  return (
    <>
      <section className="list-hero dashboard-hero">
        <span className="eyebrow">painel operacional</span>
        <h1>Dados extraidos pelo ScaleScrape</h1>
        <p>
          Acompanhe jobs, veja registros persistidos no Postgres e dispare uma consulta imediata nos dois alvos.
        </p>
      </section>

      <main className="content dashboard-content">
        {apiError ? <div className="dashboard-alert">API indisponivel: {apiError}</div> : null}
        {createdJobs ? <div className="dashboard-alert success">Jobs criados agora: {createdJobs}</div> : null}

        <section className="dashboard-actions" aria-label="Criar scraping agora">
          <form action="/dashboard/run" method="post">
            <input type="hidden" name="source" value="fake-target" />
            <button type="submit">Consultar target agora</button>
          </form>
          <form action="/dashboard/run" method="post">
            <input type="hidden" name="source" value="books-to-scrape" />
            <button type="submit">Consultar Books agora</button>
          </form>
          <form action="/dashboard/run" method="post">
            <input type="hidden" name="source" value="all" />
            <button type="submit">Consultar os dois agora</button>
          </form>
          <a className="secondary-dashboard-action" href="/dashboard">Atualizar painel</a>
        </section>

        <section className="dashboard-metrics" aria-label="Resumo do scraping">
          <div className="dashboard-metric"><strong>{jobs.length}</strong><span>jobs recentes</span></div>
          <div className="dashboard-metric"><strong>{items.length}</strong><span>itens listados</span></div>
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

        <section className="dashboard-section">
          <div className="section-head">
            <div>
              <h2>Registros extraidos</h2>
              <p>Tabela alimentada por `scraped_items`, incluindo preco convertido, nota e descricao quando a fonte e Books.</p>
            </div>
          </div>
          <div className="table-wrap">
            <table className="dashboard-table extracted-table">
              <thead>
                <tr>
                  <th>Fonte</th>
                  <th>Titulo</th>
                  <th>Preco</th>
                  <th>Nota</th>
                  <th>Descricao</th>
                  <th>Extraido em</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{itemSource(item)}</td>
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
        </section>
      </main>
    </>
  );
}
