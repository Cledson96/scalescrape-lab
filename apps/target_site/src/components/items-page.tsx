import React from "react";

import type { RecordPage } from "../lib/data";

type ItemsPageProps = {
  title: string;
  subtitle: string;
  page: RecordPage;
  route: string;
  detailRoute: string;
};

export function ItemsPage({ title, subtitle, page, route, detailRoute }: ItemsPageProps) {
  return (
    <>
      <section className="list-hero">
        <span className="eyebrow">consulta operacional</span>
        <h1>{title}</h1>
        <p>
          {subtitle} Pagina {page.pageNumber} de {page.totalPages}, {page.total} registros.
        </p>
      </section>
      <main className="content">
        <section className="items-grid">
          {page.records.map((record) => (
            <article className="item-card" data-item-id={record.externalId} key={record.externalId}>
              <div className="tag-row">
                <span className="tag blue">{record.sourceLabel}</span>
                <span className="tag green">{record.status}</span>
              </div>
              <h2 className="item-title">{record.title}</h2>
              <div className="item-meta">
                <span>{record.category}</span>
                <span>{record.region}</span>
                <span>score de risco: {record.riskScore}</span>
                {record.fetchedAt ? <span>extraido em: {new Date(record.fetchedAt).toLocaleString("pt-BR")}</span> : null}
              </div>
              <div className="risk" aria-hidden="true">
                <span style={{ width: `${Math.max(4, Math.min(100, record.riskScore))}%` }} />
              </div>
              <a className="detail-link" href={`${detailRoute}/${record.externalId}`}>Detalhe</a>
            </article>
          ))}
        </section>
        <nav className="pager" aria-label="Paginacao">
          <span>
            {page.hasPrevious ? (
              <a className="prev-page" href={`${route}?page=${page.pageNumber - 1}`}>Pagina anterior</a>
            ) : null}
          </span>
          <span>
            {page.hasNext ? (
              <a className="next-page" href={`${route}?page=${page.pageNumber + 1}`}>Proxima</a>
            ) : null}
          </span>
        </nav>
      </main>
    </>
  );
}
