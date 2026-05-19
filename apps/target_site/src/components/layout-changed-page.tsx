import React from "react";

export function LayoutChangedPage() {
  return (
    <main className="content">
      <section className="detail-panel changed-layout">
        <div className="tag-row"><span className="tag amber">selector drift</span></div>
        <h1>Layout alterado</h1>
        <p>Pagina propositalmente fora do contrato dos seletores para validar alerta, fallback e investigacao.</p>
        <div data-record="layout-1">Registro sem seletores esperados</div>
      </section>
    </main>
  );
}
