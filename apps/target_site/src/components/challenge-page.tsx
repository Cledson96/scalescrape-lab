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
        <p>Este captcha pertence ao proprio laboratorio e usa resposta fixa para o mock resolver.</p>
      </section>
    </main>
  );
}
