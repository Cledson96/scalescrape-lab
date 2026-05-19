import React from "react";

type HomePageProps = {
  localTotal: number;
  externalTotal: number;
};

const scenarios = [
  {
    title: "Dataset publico",
    href: "/items?page=1",
    description: "Consulta estavel para scraping paginado com seletores previsiveis.",
    tag: "200 OK",
    tone: "green"
  },
  {
    title: "Monitoramento anti-fraude",
    href: "/protected/items?page=1",
    description: "Sessao, score de risco, delay e challenge local para simular protecao.",
    tag: "policy",
    tone: "blue"
  },
  {
    title: "Massa fake externa",
    href: "/external/items?page=1",
    description: "RandomUser normalizado como dados cadastrais sinteticos com fallback.",
    tag: "bulk data",
    tone: "green"
  },
  {
    title: "Dashboard de extracao",
    href: "/dashboard",
    description: "Tabelas das quatro fontes salvas no banco e botoes para executar coletas agora.",
    tag: "Postgres",
    tone: "blue"
  },
  {
    title: "Rate limit",
    href: "/rate-limited/items",
    description: "Resposta 429 para retry, backoff e cooldown de proxy.",
    tag: "429",
    tone: "amber"
  },
  {
    title: "Bloqueio",
    href: "/forbidden/items",
    description: "Resposta 403 para testar bloqueio e politica de interrupcao.",
    tag: "403",
    tone: "red"
  },
  {
    title: "Layout alterado",
    href: "/layout-changed/items",
    description: "Pagina sem seletores esperados para validar deteccao de drift.",
    tag: "selector drift",
    tone: "amber"
  }
];

export function HomePage({ localTotal, externalTotal }: HomePageProps) {
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">inspirado em protecao ao credito e prevencao a fraudes</span>
          <h1>Controle riscos e fraudes em um laboratorio de scraping observavel</h1>
          <p>
            Um target-site local para demonstrar coleta em escala, monitoramento continuo, sinais de risco e
            politicas de seguranca sem tocar em dados pessoais reais.
          </p>
          <div className="hero-actions">
            <a className="primary-action" href="/items?page=1">Testar dataset</a>
            <a className="secondary-action" href="/dashboard">Ver dashboard</a>
          </div>
        </div>
        <div className="status-board" aria-label="Resumo do laboratorio">
          <div className="metric"><strong>{localTotal}</strong><span>registros locais</span></div>
          <div className="metric"><strong>{externalTotal}</strong><span>registros fake externos</span></div>
          <div className="metric"><strong>6</strong><span>cenarios de teste</span></div>
          <div className="metric"><strong>0</strong><span>dados pessoais reais</span></div>
        </div>
      </section>
      <main className="content">
        <div className="section-head">
          <div>
            <h2>Simulador cadastral e antifraude</h2>
            <p>Rotas prontas para API, worker, Playwright, retry, DLQ e observabilidade.</p>
          </div>
        </div>
        <section className="scenario-grid">
          {scenarios.map((scenario) => (
            <a className="scenario-card" href={scenario.href} key={scenario.href}>
              <div>
                <h3>{scenario.title}</h3>
                <p>{scenario.description}</p>
              </div>
              <div className="tag-row">
                <span className={`tag ${scenario.tone}`}>{scenario.tag}</span>
              </div>
            </a>
          ))}
        </section>
      </main>
    </>
  );
}
