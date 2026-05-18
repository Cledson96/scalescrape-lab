import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { HomePage } from "../src/components/home-page";
import { ItemsPage } from "../src/components/items-page";
import { LoginPage } from "../src/components/login-page";
import { DashboardPage } from "../src/components/dashboard-page";
import { Shell } from "../src/components/shell";
import { getLocalRecords, paginateRecords } from "../src/lib/data";

test("home renders Procob-inspired scenario links", () => {
  const html = renderToStaticMarkup(
    <Shell>
      <HomePage localTotal={240} externalTotal={500} />
    </Shell>
  );

  assert.match(html, /ScaleScrape Target Lab/);
  assert.match(html, /Controle riscos e fraudes/);
  assert.match(html, /href="\/items\?page=1"/);
  assert.match(html, /href="\/protected\/items\?page=1"/);
  assert.match(html, /href="\/external\/items\?page=1"/);
  assert.match(html, /href="\/dashboard"/);
});

test("items page preserves scraper selectors", () => {
  const records = getLocalRecords({ prefix: "normal", total: 15 });
  const page = paginateRecords(records, 1, 5);
  const html = renderToStaticMarkup(
    <ItemsPage
      title="Dataset publico"
      subtitle="Fonte local estavel"
      page={page}
      route="/items"
      detailRoute="/items"
    />
  );

  assert.match(html, /class="item-card/);
  assert.match(html, /class="item-title/);
  assert.match(html, /class="detail-link/);
  assert.match(html, /class="next-page/);
  assert.match(html, /data-item-id="normal-1"/);
});

test("login page renders form and reCAPTCHA widget used by the worker", () => {
  const html = renderToStaticMarkup(
    <LoginPage recaptchaSiteKey="6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI" nextPath="/protected/items?page=1" />
  );

  assert.match(html, /id="login-form"/);
  assert.match(html, /name="username"/);
  assert.match(html, /name="password"/);
  assert.match(html, /id="captcha-challenge"/);
  assert.match(html, /data-challenge-id="recaptcha"/);
  assert.match(html, /g-recaptcha/);
  assert.match(html, /data-sitekey="6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"/);
});

test("dashboard renders extracted items table and immediate scrape actions", () => {
  const html = renderToStaticMarkup(
    <DashboardPage
      activeTab="betano"
      jobs={[
        {
          id: 12,
          source_id: 1,
          start_url: "http://target-site:4000/protected/items?page=1",
          public_url: "https://dev.scalescrape.cledson.com.br/protected/items?page=1",
          status: "success",
          mode: "browser",
          max_pages: 1,
          items_found: 12,
          error_message: null,
          created_at: "2026-05-18T21:52:13.392016"
        }
      ]}
      items={[
        {
          id: 99,
          job_id: 17,
          external_id: "join_902",
          title: "Join",
          detail_url: "https://books.toscrape.com/catalogue/join_902/index.html",
          public_detail_url: "https://books.toscrape.com/catalogue/join_902/index.html",
          raw_data: {
            source: "books-to-scrape",
            price: { formatted: "£35.67", brl_formatted: "R$ 231,86" },
            rating: { label: "Five", value: 5 },
            description: "What if you could live multiple lives simultaneously?"
          },
          created_at: "2026-05-18T21:39:14.229704",
          extracted_at: "2026-05-18T21:39:14.229704"
        }
      ]}
      fakeItems={{
        items: [
          {
            id: 10,
            job_id: 12,
            external_id: "protected-1",
            title: "Empresa Aurora",
            detail_url: "http://target-site:4000/items/protected-1",
            public_detail_url: "https://dev.scalescrape.cledson.com.br/items/protected-1",
            raw_data: { source: "fake-target", category: "score alto" },
            created_at: "2026-05-18T21:39:14.229704",
            extracted_at: "2026-05-18T21:39:14.229704"
          }
        ],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1
      }}
      booksItems={{
        items: [
          {
            id: 99,
            job_id: 17,
            external_id: "join_902",
            title: "Join",
            detail_url: "https://books.toscrape.com/catalogue/join_902/index.html",
            public_detail_url: "https://books.toscrape.com/catalogue/join_902/index.html",
            raw_data: {
              source: "books-to-scrape",
              price: { formatted: "£35.67", brl_formatted: "R$ 231,86" },
              rating: { label: "Five", value: 5 },
              description: "What if you could live multiple lives simultaneously?"
            },
            created_at: "2026-05-18T21:39:14.229704",
            extracted_at: "2026-05-18T21:39:14.229704"
          }
        ],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1
      }}
      globoItems={{
        items: [
          {
            id: 120,
            job_id: 18,
            external_id: "g1-globo-com-saude-remedio",
            title: "Remedio recolhido",
            detail_url: "https://g1.globo.com/saude/noticia/2026/05/18/remedio.ghtml",
            public_detail_url: "https://g1.globo.com/saude/noticia/2026/05/18/remedio.ghtml",
            public_image_url: "https://api-dev.scalescrape.cledson.com.br/media/globo/remedio.jpg",
            raw_data: {
              source: "globo-home",
              category: "jornalismo",
              description: "Resumo da noticia para o dashboard."
            },
            created_at: "2026-05-18T21:39:14.229704",
            extracted_at: "2026-05-18T21:39:14.229704"
          }
        ],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1
      }}
      betanoItems={{
        items: [
          {
            id: 220,
            job_id: 31,
            external_id: "betano-ponte-preta-vs-londrina",
            title: "Ponte Preta vs Londrina-PR",
            detail_url: "https://www.betano.bet.br/odds/ponte-preta-londrina",
            public_detail_url: "https://www.betano.bet.br/odds/ponte-preta-londrina",
            raw_data: {
              source: "betano-football",
              championship: "Brasil - Brasileirao - Serie B",
              home_team: "Ponte Preta",
              away_team: "Londrina-PR",
              match_date: "18/05",
              match_time: "45:00",
              market_type: "Resultado da partida",
              odds: {
                home_raw: "6.30",
                draw_raw: "3.25",
                away_raw: "1.65"
              },
              extracted_at: "2026-05-18T22:51:06.755533"
            },
            created_at: "2026-05-18T22:51:06.755533",
            extracted_at: "2026-05-18T22:51:06.755533"
          }
        ],
        total: 1,
        page: 2,
        page_size: 10,
        total_pages: 3
      }}
    />
  );

  assert.match(html, /Dados extraidos pelo ScaleScrape/);
  assert.match(html, /Consultar fake agora/);
  assert.match(html, /Consultar Books agora/);
  assert.match(html, /Consultar Globo agora/);
  assert.match(html, /Consultar Betano agora/);
  assert.match(html, /Consultar todos agora/);
  assert.match(html, /href="\/dashboard\?tab=fake&amp;betanoPage=2"/);
  assert.match(html, /href="\/dashboard\?tab=books&amp;betanoPage=2"/);
  assert.match(html, /href="\/dashboard\?tab=globo&amp;betanoPage=2"/);
  assert.match(html, /href="\/dashboard\?tab=betano&amp;betanoPage=2"/);
  assert.match(html, /class="[^"]*dashboard-tab[^"]*active[^"]*"/);
  assert.doesNotMatch(html, /Registros coletados apos login/);
  assert.match(html, /Site fake/);
  assert.match(html, /Books/);
  assert.match(html, /Globo/);
  assert.match(html, /Betano futebol/);
  assert.match(html, /https:\/\/dev\.scalescrape\.cledson\.com\.br\/protected\/items\?page=1/);
  assert.doesNotMatch(html, /£35.67 \/ R\$ 231,86/);
  assert.doesNotMatch(html, /Resumo da noticia para o dashboard/);
  assert.match(html, /Brasil - Brasileirao - Serie B/);
  assert.match(html, /Ponte Preta x Londrina-PR/);
  assert.match(html, /Resultado da partida/);
  assert.match(html, /6.30/);
  assert.match(html, /3.25/);
  assert.match(html, /1.65/);
  assert.match(html, /href="\/dashboard\?tab=betano&amp;betanoPage=1"/);
  assert.match(html, /href="\/dashboard\?tab=betano&amp;betanoPage=3"/);
});
