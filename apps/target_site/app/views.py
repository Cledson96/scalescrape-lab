from __future__ import annotations

from html import escape


def layout(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html lang="pt-BR">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{escape(title)}</title>
        <style>
          :root {{
            color-scheme: light;
            --ink: #16202a;
            --muted: #5b6875;
            --line: #d8e0e8;
            --panel: #ffffff;
            --page: #eef3f7;
            --blue: #1769aa;
            --green: #1f8a5b;
            --amber: #b7791f;
            --red: #b42318;
            --teal: #0f766e;
          }}
          * {{ box-sizing: border-box; }}
          body {{
            margin: 0;
            background: var(--page);
            color: var(--ink);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.5;
          }}
          a {{ color: inherit; }}
          .shell {{ min-height: 100vh; }}
          .topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            padding: 18px clamp(18px, 4vw, 54px);
            background: #111827;
            color: #ffffff;
            border-bottom: 4px solid #2dd4bf;
          }}
          .brand {{ display: flex; align-items: center; gap: 12px; font-weight: 800; letter-spacing: 0; }}
          .brand-mark {{
            width: 34px;
            height: 34px;
            display: grid;
            place-items: center;
            border: 1px solid rgba(255, 255, 255, 0.28);
            background: #1f2937;
            font-size: 16px;
            font-weight: 900;
          }}
          .nav {{ display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }}
          .nav a {{
            padding: 8px 10px;
            border: 1px solid rgba(255, 255, 255, 0.22);
            text-decoration: none;
            font-size: 14px;
            background: rgba(255, 255, 255, 0.06);
          }}
          .hero {{
            display: grid;
            grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
            gap: 28px;
            padding: clamp(28px, 6vw, 72px) clamp(18px, 4vw, 54px) 34px;
            background: linear-gradient(135deg, #ffffff 0%, #edf7f5 45%, #f7efe3 100%);
            border-bottom: 1px solid var(--line);
          }}
          .hero h1 {{
            max-width: 820px;
            margin: 0 0 16px;
            font-size: clamp(34px, 5vw, 64px);
            line-height: 1.02;
            letter-spacing: 0;
          }}
          .hero p {{ max-width: 760px; margin: 0; color: var(--muted); font-size: 18px; }}
          .status-board {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            align-self: end;
          }}
          .metric {{
            min-height: 92px;
            padding: 16px;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
          }}
          .metric strong {{ display: block; font-size: 30px; line-height: 1; }}
          .metric span {{ color: var(--muted); font-size: 13px; }}
          .content {{ padding: 30px clamp(18px, 4vw, 54px) 56px; }}
          .section-head {{ display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 16px; }}
          .section-head h2 {{ margin: 0; font-size: 24px; }}
          .section-head p {{ margin: 0; color: var(--muted); }}
          .scenario-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; }}
          .scenario-card {{
            display: flex;
            min-height: 150px;
            flex-direction: column;
            justify-content: space-between;
            gap: 16px;
            padding: 18px;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            text-decoration: none;
          }}
          .scenario-card:hover {{ border-color: #7aa7c7; transform: translateY(-1px); }}
          .scenario-card h3 {{ margin: 0 0 6px; font-size: 18px; }}
          .scenario-card p {{ margin: 0; color: var(--muted); font-size: 14px; }}
          .tag-row {{ display: flex; gap: 8px; flex-wrap: wrap; }}
          .tag {{
            display: inline-flex;
            width: fit-content;
            padding: 4px 8px;
            border: 1px solid var(--line);
            background: #f8fafc;
            color: #334155;
            font-size: 12px;
          }}
          .tag.green {{ border-color: #9fd4be; color: var(--green); background: #eefbf4; }}
          .tag.blue {{ border-color: #a8cbe8; color: var(--blue); background: #eef6fc; }}
          .tag.amber {{ border-color: #e4c281; color: var(--amber); background: #fff8e8; }}
          .tag.red {{ border-color: #efaaa3; color: var(--red); background: #fff1ef; }}
          .list-hero {{
            padding: 32px clamp(18px, 4vw, 54px);
            background: #ffffff;
            border-bottom: 1px solid var(--line);
          }}
          .list-hero h1 {{ margin: 0 0 8px; font-size: clamp(30px, 4vw, 46px); letter-spacing: 0; }}
          .list-hero p {{ margin: 0; color: var(--muted); }}
          .items-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }}
          .item-card {{
            min-height: 210px;
            padding: 18px;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            gap: 14px;
          }}
          .item-title {{ margin: 0; font-size: 19px; line-height: 1.25; letter-spacing: 0; }}
          .item-meta {{ display: grid; gap: 8px; color: var(--muted); font-size: 14px; }}
          .risk {{
            height: 8px;
            width: 100%;
            overflow: hidden;
            background: #e6edf3;
            border: 1px solid #d3dee8;
          }}
          .risk span {{ display: block; height: 100%; background: linear-gradient(90deg, #1f8a5b, #b7791f, #b42318); }}
          .detail-link, .next-page, .prev-page {{
            display: inline-flex;
            width: fit-content;
            margin-top: auto;
            padding: 9px 12px;
            background: #111827;
            color: #ffffff;
            text-decoration: none;
            font-weight: 700;
            font-size: 14px;
          }}
          .pager {{ display: flex; justify-content: space-between; gap: 12px; margin-top: 22px; flex-wrap: wrap; }}
          .detail-panel {{
            max-width: 920px;
            margin: 0 auto;
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: clamp(20px, 4vw, 34px);
          }}
          .detail-panel h1 {{ margin-top: 0; }}
          .debug-table {{ width: 100%; border-collapse: collapse; background: #ffffff; border: 1px solid var(--line); }}
          .debug-table th, .debug-table td {{ padding: 10px; border-bottom: 1px solid var(--line); text-align: left; }}
          @media (max-width: 760px) {{
            .topbar {{ align-items: flex-start; flex-direction: column; }}
            .nav {{ justify-content: flex-start; }}
            .hero {{ grid-template-columns: 1fr; }}
            .status-board {{ grid-template-columns: 1fr 1fr; }}
          }}
        </style>
      </head>
      <body>
        <div class="shell">
          <header class="topbar">
            <a class="brand" href="/">
              <span class="brand-mark">SS</span>
              <span>ScaleScrape Target Lab</span>
            </a>
            <nav class="nav" aria-label="Cenarios">
              <a href="/items?page=1">Publico</a>
              <a href="/protected/items?page=1">Protegido</a>
              <a href="/external/items?page=1">Fonte externa</a>
              <a href="/antibot/debug/session">Debug</a>
            </nav>
          </header>
          {body}
        </div>
      </body>
    </html>
    """


def render_home(local_total: int, external_total: int) -> str:
    cards = [
        scenario_card("Dataset publico", "/items?page=1", "Pagina estavel para scraping com paginacao.", "green", "200 OK"),
        scenario_card("Anti-bot local", "/protected/items?page=1", "Sessao, risco, delay e challenge proprio.", "blue", "policy"),
        scenario_card("Fonte fake externa", "/external/items?page=1", "RandomUser normalizado com fallback local.", "green", "bulk data"),
        scenario_card("Rate limit", "/rate-limited/items", "Resposta 429 para retry e cooldown de proxy.", "amber", "429"),
        scenario_card("Bloqueio", "/forbidden/items", "Resposta 403 para fluxo de bloqueio controlado.", "red", "403"),
        scenario_card("Layout alterado", "/layout-changed/items", "Pagina sem seletores esperados para teste de resiliencia.", "amber", "selector drift"),
    ]
    body = f"""
      <section class="hero">
        <div>
          <h1>ScaleScrape Target Lab</h1>
          <p>Ambiente local para demonstrar scraping em escala com paginas publicas, cenarios anti-bot, massa fake e sinais observaveis de bloqueio.</p>
        </div>
        <div class="status-board" aria-label="Resumo do laboratorio">
          <div class="metric"><strong>{local_total}</strong><span>registros locais</span></div>
          <div class="metric"><strong>{external_total}</strong><span>registros fake externos</span></div>
          <div class="metric"><strong>6</strong><span>cenarios de teste</span></div>
          <div class="metric"><strong>0</strong><span>dados pessoais reais</span></div>
        </div>
      </section>
      <main class="content">
        <div class="section-head">
          <div>
            <h2>Cenarios do simulador</h2>
            <p>Rotas prontas para API, worker, Playwright, retry, DLQ e observabilidade.</p>
          </div>
        </div>
        <section class="scenario-grid">
          {''.join(cards)}
        </section>
      </main>
    """
    return layout("ScaleScrape Target Lab", body)


def scenario_card(title: str, href: str, description: str, color: str, tag: str) -> str:
    return f"""
    <a class="scenario-card" href="{escape(href)}">
      <div>
        <h3>{escape(title)}</h3>
        <p>{escape(description)}</p>
      </div>
      <div class="tag-row"><span class="tag {escape(color)}">{escape(tag)}</span></div>
    </a>
    """


def render_items_page(title: str, subtitle: str, page, route: str, detail_route: str = "/items") -> str:
    cards = [render_item_card(record, detail_route=detail_route) for record in page.records]
    prev_link = ""
    next_link = ""
    if page.has_previous:
        prev_link = f'<a class="prev-page" href="{escape(route)}?page={page.page_number - 1}">Pagina anterior</a>'
    if page.has_next:
        next_link = f'<a class="next-page" href="{escape(route)}?page={page.page_number + 1}">Proxima</a>'
    body = f"""
      <section class="list-hero">
        <h1>{escape(title)}</h1>
        <p>{escape(subtitle)} Pagina {page.page_number} de {page.total_pages}, {page.total} registros.</p>
      </section>
      <main class="content">
        <section class="items-grid">
          {''.join(cards)}
        </section>
        <nav class="pager" aria-label="Paginacao">
          <span>{prev_link}</span>
          <span>{next_link}</span>
        </nav>
      </main>
    """
    return layout(title, body)


def render_item_card(record, detail_route: str = "/items") -> str:
    width = max(4, min(100, int(record.risk_score)))
    href = f"{detail_route}/{record.external_id}"
    return f"""
    <article class="item-card" data-item-id="{escape(record.external_id)}">
      <div class="tag-row">
        <span class="tag blue">{escape(record.source_label)}</span>
        <span class="tag green">{escape(record.status)}</span>
      </div>
      <h2 class="item-title">{escape(record.title)}</h2>
      <div class="item-meta">
        <span>{escape(record.category)}</span>
        <span>{escape(record.region)}</span>
        <span>score de risco: {record.risk_score}</span>
      </div>
      <div class="risk" aria-hidden="true"><span style="width: {width}%"></span></div>
      <a class="detail-link" href="{escape(href)}">Detalhe</a>
    </article>
    """


def render_detail_page(record) -> str:
    if record is None:
        body = """
        <main class="content">
          <section class="detail-panel">
            <h1>Registro nao encontrado</h1>
            <p>O identificador informado nao existe no dataset atual.</p>
          </section>
        </main>
        """
        return layout("Registro nao encontrado", body)
    body = f"""
    <main class="content">
      <section class="detail-panel item-detail" data-item-id="{escape(record.external_id)}">
        <div class="tag-row">
          <span class="tag blue">{escape(record.source_label)}</span>
          <span class="tag green">{escape(record.status)}</span>
        </div>
        <h1>Detalhe {escape(record.external_id)}</h1>
        <h2>{escape(record.title)}</h2>
        <p class="status">{escape(record.category)} em {escape(record.region)}</p>
        <p>{escape(record.raw_summary)}</p>
        <a class="detail-link" href="/items?page=1">Voltar para dataset</a>
      </section>
    </main>
    """
    return layout(f"Detalhe {record.external_id}", body)


def render_challenge_page(challenge_id: str) -> str:
    body = f"""
    <main class="content">
      <section id="captcha-challenge" class="detail-panel" data-challenge-id="{escape(challenge_id)}">
        <div class="tag-row"><span class="tag amber">challenge local</span></div>
        <h1>Verificacao local</h1>
        <img id="captcha-image" src="/captcha/image/{escape(challenge_id)}" alt="captcha local" />
        <p>Este captcha pertence ao proprio laboratorio.</p>
      </section>
    </main>
    """
    return layout("Challenge local", body)


def render_layout_changed_page() -> str:
    body = """
    <main class="content">
      <section class="detail-panel changed-layout">
        <div class="tag-row"><span class="tag amber">selector drift</span></div>
        <h1>Layout alterado</h1>
        <div data-record="layout-1">Registro sem seletores esperados</div>
      </section>
    </main>
    """
    return layout("Layout alterado", body)
