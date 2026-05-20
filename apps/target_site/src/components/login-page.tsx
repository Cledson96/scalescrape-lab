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
          <h1>Portal protegido do simulador antifraude</h1>
          <p>
            Esta etapa simula um portal cadastral protegido: o worker precisa autenticar,
            validar o desafio configuravel do laboratorio e continuar a coleta.
          </p>
          <ul className="login-proof-list">
            <li>Validacao server-side de credenciais e token</li>
            <li>Cookie de sessao antes das rotas protegidas</li>
            <li>Fluxo realista para Playwright e politica anti-bot</li>
          </ul>
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
              <strong>Desafio configuravel</strong>
              <span>Fluxo controlado para validar token, sessao e continuidade da automacao.</span>
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
