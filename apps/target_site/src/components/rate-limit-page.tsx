import React from "react";

type RateLimitPageProps = {
  reason: string;
  riskScore: number;
};

export function RateLimitPage({ reason, riskScore }: RateLimitPageProps) {
  return (
    <main className="content">
      <section className="detail-panel" data-antibot-action="rate_limit">
        <div className="tag-row"><span className="tag red">rate limit ativo</span></div>
        <h1>Coleta temporariamente limitada</h1>
        <p>
          O simulador bloqueou esta sessao por volume excessivo de requisicoes. Aguarde a janela operacional
          expirar antes de tentar novamente.
        </p>
        <p><strong>Motivo:</strong> {reason}</p>
        <p><strong>Score de risco:</strong> {riskScore}</p>
      </section>
    </main>
  );
}
