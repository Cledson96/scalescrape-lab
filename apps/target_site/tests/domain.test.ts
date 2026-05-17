import assert from "node:assert/strict";
import test from "node:test";

import {
  getLocalRecords,
  normalizeRandomUserPayload,
  paginateRecords
} from "../src/lib/data";
import { AntibotAction, AntibotSimulator } from "../src/lib/antibot";
import { CaptchaStore } from "../src/lib/captcha";

test("local fake records are deterministic and large enough for scale demo", () => {
  const first = getLocalRecords({ prefix: "normal", total: 240 });
  const second = getLocalRecords({ prefix: "normal", total: 240 });

  assert.equal(first.length, 240);
  assert.equal(first[0]?.externalId, "normal-1");
  assert.equal(first[0]?.title, second[0]?.title);
  assert.notEqual(first[0]?.title, first[1]?.title);
});

test("pagination returns the expected slice and navigation state", () => {
  const records = getLocalRecords({ prefix: "normal", total: 25 });
  const page = paginateRecords(records, 2, 10);

  assert.deepEqual(
    page.records.map((record) => record.externalId),
    Array.from({ length: 10 }, (_, index) => `normal-${index + 11}`)
  );
  assert.equal(page.total, 25);
  assert.equal(page.totalPages, 3);
  assert.equal(page.hasNext, true);
  assert.equal(page.hasPrevious, true);
});

test("randomuser payload is normalized without sensitive contact fields", () => {
  const records = normalizeRandomUserPayload({
    results: [
      {
        gender: "female",
        nat: "BR",
        dob: { age: 32 },
        location: {
          city: "Curitiba",
          state: "Parana",
          country: "Brazil",
          timezone: { description: "Brasilia" }
        },
        email: "fake@example.test",
        phone: "000"
      }
    ]
  });

  assert.equal(records.length, 1);
  assert.equal(records[0]?.externalId, "external-1");
  assert.match(records[0]?.title ?? "", /Brazil/);
  assert.doesNotMatch(records[0]?.rawSummary ?? "", /fake@example\.test/);
  assert.doesNotMatch(records[0]?.rawSummary ?? "", /000/);
});

test("antibot simulator challenges suspicious high-volume sessions", () => {
  const simulator = new AntibotSimulator();
  let action = AntibotAction.Allow;

  for (let index = 0; index < 8; index += 1) {
    action = simulator.evaluate({
      sessionId: "session-a",
      proxyId: "proxy-a",
      path: "/protected/items",
      userAgent: "SuspiciousBot/1.0",
      hasClearanceCookie: false,
      now: new Date(Date.UTC(2026, 0, 1, 10, 0, index))
    }).action;
  }

  assert.equal(action, AntibotAction.Challenge);
});

test("captcha store accepts the mock resolver answer used by the worker", () => {
  const store = new CaptchaStore();
  const challenge = store.create();

  assert.equal(challenge.expectedAnswer, "ABCDE");
  assert.equal(store.verify(challenge.challengeId, "abcde"), true);
  assert.equal(store.verify(challenge.challengeId, "abcde"), false);
});
