
type HomePageProps = {
  localTotal: number;
  externalTotal: number;
};

const scenarios = [
  {
    title: "Dataset publico controlado",
    href: "/items?page=1",
    description: "Consulta estavel, paginada e deterministica para validar throughput sem depender de terceiros.",
    tag: "200 OK",
    tone: "green"
  },
  {
    title: "Portal protegido anti-fraude",
    href: "/protected/items?page=1",
    description: "Login, cookies, score de risco, delay e challenge local para provar dominio de sessao.",
    tag: "policy",
    tone: "blue"
  },
  {
    title: "Massa externa normalizada",
    href: "/external/items?page=1",
    description: "Payload externo convertido em registros sinteticos, sem expor contato ou documento.",
    tag: "bulk data",
    tone: "green"
  },
  {
    title: "Centro de comando",
    href: "/dashboard",
    description: "Tabelas das quatro fontes, disparo de jobs e visao operacional para apresentar a arquitetura.",
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
          <span className="eyebrow">case autoral para scraping, risco e monitoramento continuo</span>
          <h1>Controle riscos e fraudes em um laboratorio de scraping observavel</h1>
          <p>
            Uma vitrine tecnica inspirada em plataformas de protecao ao credito: coleta em escala, dominio de HTTP,
            workers paralelos, sinais de risco e politicas anti-bot sem tocar em dados pessoais reais.
          </p>
          <div className="hero-actions">
            <a className="primary-action" href="/dashboard">Abrir centro de comando</a>
            <a className="secondary-action" href="/items?page=1">Testar dataset</a>
          </div>
        </div>
        <div className="status-board" aria-label="Resumo do laboratorio">
          <div className="status-card wide">
            <span>pipeline demonstrado</span>
            <strong>API + RabbitMQ + Workers + Postgres</strong>
            <p>Fluxo completo para falar de latencia, throughput, retry, timeout e observabilidade.</p>
          </div>
          <div className="metric"><strong>{localTotal}</strong><span>registros locais</span></div>
          <div className="metric"><strong>{externalTotal}</strong><span>registros fake externos</span></div>
          <div className="metric"><strong>7</strong><span>cenarios de teste</span></div>
          <div className="metric"><strong>0</strong><span>dados pessoais reais</span></div>
        </div>
      </section>
      <main className="content">
        <div className="section-head">
          <div>
            <span className="section-kicker">ambiente de entrevista</span>
            <h2>Simulador cadastral e antifraude</h2>
            <p>Rotas prontas para API, worker, Playwright, retry, DLQ, proxy policy e observabilidade.</p>
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
