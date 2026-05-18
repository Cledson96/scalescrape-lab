import React from "react";

type LoginPageProps = {
  challengeId: string;
  nextPath: string;
  error?: string;
};

export function LoginPage({ challengeId, nextPath, error }: LoginPageProps) {
  return (
    <main className="content">
      <section className="login-panel">
        <div>
          <span className="eyebrow">acesso protegido</span>
          <h1>Login do simulador antifraude</h1>
          <p>
            Esta etapa simula um portal cadastral protegido: o worker precisa autenticar,
            resolver o captcha proprio do laboratorio e continuar a coleta.
          </p>
        </div>
        <form id="login-form" className="login-form" action="/login/submit" method="post">
          <input type="hidden" name="next" value={nextPath} />
          <input type="hidden" name="challenge_id" value={challengeId} />

          <label>
            Usuario
            <input name="username" autoComplete="username" defaultValue="demo" />
          </label>

          <label>
            Senha
            <input name="password" type="password" autoComplete="current-password" defaultValue="demo123" />
          </label>

          <section id="captcha-challenge" data-challenge-id={challengeId} className="captcha-box">
            <div>
              <strong>Captcha local</strong>
              <span>Resolvido por mock ou 2Captcha real quando habilitado.</span>
            </div>
            <img id="captcha-image" src={`/captcha/image/${challengeId}`} alt="captcha local" />
            <label>
              Resposta do captcha
              <input name="captcha_answer" autoComplete="off" />
            </label>
          </section>

          {error ? <p className="form-error">Credenciais ou captcha invalidos.</p> : null}

          <button type="submit">Entrar no ambiente protegido</button>
        </form>
      </section>
    </main>
  );
}
