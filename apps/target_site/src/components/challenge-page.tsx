import React from "react";

type ChallengePageProps = {
  challengeId: string;
};

export function ChallengePage({ challengeId }: ChallengePageProps) {
  return (
    <main className="content">
      <section id="captcha-challenge" className="detail-panel" data-challenge-id={challengeId}>
        <div className="tag-row"><span className="tag amber">challenge local</span></div>
        <h1>Verificacao local</h1>
        <img id="captcha-image" src={`/captcha/image/${challengeId}`} alt="captcha local" />
        <p>Este captcha pertence ao proprio laboratorio e comprova o fluxo de challenge, solver mockado e liberacao controlada da sessao.</p>
      </section>
    </main>
  );
}
