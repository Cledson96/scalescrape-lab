import React from "react";

type LoginPageProps = {
  recaptchaSiteKey: string;
  nextPath: string;
  error?: string;
};

export function LoginPage({ recaptchaSiteKey, nextPath, error }: LoginPageProps) {
  return (
    <main className="content">
      <section className="login-panel">
        <div>
          <span className="eyebrow">acesso protegido</span>
          <h1>Login do simulador antifraude</h1>
          <p>
            Esta etapa simula um portal cadastral protegido: o worker precisa autenticar,
            resolver o reCAPTCHA do Google e continuar a coleta.
          </p>
        </div>
        <form id="login-form" className="login-form" action="/login/submit" method="post">
          <input type="hidden" name="next" value={nextPath} />

          <label>
            Usuario
            <input name="username" autoComplete="username" defaultValue="demo" />
          </label>

          <label>
            Senha
            <input name="password" type="password" autoComplete="current-password" defaultValue="demo123" />
          </label>

          <section id="captcha-challenge" data-challenge-id="recaptcha" className="captcha-box">
            <div>
              <strong>Google reCAPTCHA</strong>
              <span>Resolvido por 2Captcha real quando habilitado, ou aceita qualquer token com chaves de teste.</span>
            </div>
            <div
              className="g-recaptcha"
              data-sitekey={recaptchaSiteKey}
            />
          </section>

          {error ? <p className="form-error">Credenciais ou captcha invalidos.</p> : null}

          <button type="submit">Entrar no ambiente protegido</button>
        </form>
      </section>
    </main>
  );
}

