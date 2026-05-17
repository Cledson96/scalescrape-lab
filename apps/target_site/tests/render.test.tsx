import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { HomePage } from "../src/components/home-page";
import { ItemsPage } from "../src/components/items-page";
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
