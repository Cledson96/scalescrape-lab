import assert from "node:assert/strict";
import test from "node:test";

import {
  getLocalRecords,
  normalizeRandomUserPayload,
  paginateRecords
} from "../src/lib/data";
import { AntibotAction, AntibotSimulator } from "../src/lib/antibot";
import { isPublicTargetPath, normalizeNextPath, validateLoginCredentials } from "../src/lib/auth";
import { CaptchaStore, captchaStore } from "../src/lib/captcha";
import { POST as submitLogin } from "../src/app/login/submit/route";

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

test("captcha store creates non-fixed answers by default", () => {
  const store = new CaptchaStore();
  const challenge = store.create();

  assert.match(challenge.expectedAnswer, /^[2-9HJKLMNPQRSTUVWXYZ]{5}$/);
  assert.notEqual(challenge.expectedAnswer, "ABCDE");
  assert.equal(store.verify(challenge.challengeId, challenge.expectedAnswer.toLowerCase()), true);
  assert.equal(store.verify(challenge.challengeId, challenge.expectedAnswer), false);
});

test("captcha store can use fixed answer for local mock runs", () => {
  const previous = process.env.TARGET_SITE_FIXED_CAPTCHA_ANSWER;
  process.env.TARGET_SITE_FIXED_CAPTCHA_ANSWER = "ABCDE";
  try {
    const store = new CaptchaStore();
    const challenge = store.create();

    assert.equal(challenge.expectedAnswer, "ABCDE");
    assert.equal(store.verify(challenge.challengeId, "abcde"), true);
  } finally {
    if (previous === undefined) {
      delete process.env.TARGET_SITE_FIXED_CAPTCHA_ANSWER;
    } else {
      process.env.TARGET_SITE_FIXED_CAPTCHA_ANSWER = previous;
    }
  }
});

test("captcha challenge can be rendered and verified across store instances", () => {
  const firstStore = new CaptchaStore();
  const secondStore = new CaptchaStore();
  const challenge = firstStore.create();

  const svg = secondStore.renderSvg(challenge.challengeId);
  for (const letter of challenge.expectedAnswer) {
    assert.match(svg, new RegExp(`>${letter}<`));
  }
  assert.equal(secondStore.verify(challenge.challengeId, challenge.expectedAnswer.toLowerCase()), true);
});

test("login credentials use env values with safe demo defaults", () => {
  assert.equal(validateLoginCredentials("demo", "demo123", {}), true);
  assert.equal(validateLoginCredentials("demo", "wrong", {}), false);
  assert.equal(
    validateLoginCredentials("cledson", "secret", {
      TARGET_SITE_USERNAME: "cledson",
      TARGET_SITE_PASSWORD: "secret"
    }),
    true
  );
});

test("login next path only allows local relative paths", () => {
  assert.equal(normalizeNextPath("/protected/items?page=1"), "/protected/items?page=1");
  assert.equal(normalizeNextPath("https://example.com/phish"), "/protected/items?page=1");
  assert.equal(normalizeNextPath("//example.com/phish"), "/protected/items?page=1");
  assert.equal(normalizeNextPath("/login?next=/admin"), "/protected/items?page=1");
});

test("target-site only leaves login, captcha and assets public", () => {
  assert.equal(isPublicTargetPath("/login"), true);
  assert.equal(isPublicTargetPath("/login/submit"), true);
  assert.equal(isPublicTargetPath("/captcha/image/challenge-1"), true);
  assert.equal(isPublicTargetPath("/captcha/verify"), true);
  assert.equal(isPublicTargetPath("/_next/static/chunk.js"), true);
  assert.equal(isPublicTargetPath("/favicon.ico"), true);

  assert.equal(isPublicTargetPath("/"), false);
  assert.equal(isPublicTargetPath("/items?page=1"), false);
  assert.equal(isPublicTargetPath("/external/items?page=1"), false);
  assert.equal(isPublicTargetPath("/protected/items?page=1"), false);
  assert.equal(isPublicTargetPath("/layout-changed/items"), false);
});

test("login submit redirects with the original request host", async () => {
  // With Google's test secret key (default), any token is accepted
  const form = new URLSearchParams({
    username: "demo",
    password: "demo123",
    "g-recaptcha-response": "test-recaptcha-token",
    next: "/protected/items?page=1"
  });
  const response = await submitLogin(
    new Request("http://localhost:4000/login/submit", {
      method: "POST",
      headers: {
        "content-type": "application/x-www-form-urlencoded",
        host: "target-site:4000"
      },
      body: form
    })
  );

  assert.equal(response.status, 303);
  assert.equal(response.headers.get("location"), "http://target-site:4000/protected/items?page=1");
});
