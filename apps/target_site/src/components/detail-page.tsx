import React from "react";

import type { PublicRecord } from "../lib/data";

type DetailPageProps = {
  record?: PublicRecord;
};

export function DetailPage({ record }: DetailPageProps) {
  if (!record) {
    return (
      <main className="content">
        <section className="detail-panel">
          <h1>Registro nao encontrado</h1>
          <p>O identificador informado nao existe no dataset atual.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="content">
      <section className="detail-panel item-detail" data-item-id={record.externalId}>
        <div className="tag-row">
          <span className="tag blue">{record.sourceLabel}</span>
          <span className="tag green">{record.status}</span>
        </div>
        <h1>Detalhe {record.externalId}</h1>
        <h2>{record.title}</h2>
        <p className="status">{record.category} em {record.region}</p>
        <div className="risk detail-risk" aria-hidden="true">
          <span style={{ width: `${Math.max(4, Math.min(100, record.riskScore))}%` }} />
        </div>
        <p>{record.rawSummary}</p>
        <a className="detail-link" href="/items?page=1">Voltar para dataset</a>
      </section>
    </main>
  );
}
