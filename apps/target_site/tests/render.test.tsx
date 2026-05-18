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
    />
  );

  assert.match(html, /Dados extraidos pelo ScaleScrape/);
  assert.match(html, /Consultar target agora/);
  assert.match(html, /Consultar Books agora/);
  assert.match(html, /Consultar os dois agora/);
  assert.match(html, /https:\/\/dev\.scalescrape\.cledson\.com\.br\/protected\/items\?page=1/);
  assert.match(html, /Join/);
  assert.match(html, /£35.67 \/ R\$ 231,86/);
  assert.match(html, /Five \(5\/5\)/);
});
