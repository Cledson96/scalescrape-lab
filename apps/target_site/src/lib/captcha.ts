import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";

export type CaptchaChallenge = {
  challengeId: string;
  expectedAnswer: string;
};

type CaptchaTokenPayload = {
  answer: string;
  issuedAt: number;
  nonce: string;
};

const maxTokenAgeMs = 15 * 60 * 1000;

function captchaSecret(): string {
  return process.env.TARGET_SITE_CAPTCHA_SECRET || "scalescrape-lab-local-captcha-secret";
}

function sign(value: string): string {
  return createHmac("sha256", captchaSecret()).update(value).digest("base64url");
}

function safeEqual(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  return leftBuffer.length === rightBuffer.length && timingSafeEqual(leftBuffer, rightBuffer);
}

function createToken(answer: string): string {
  const payload: CaptchaTokenPayload = {
    answer,
    issuedAt: Date.now(),
    nonce: randomUUID()
  };
  const encodedPayload = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  return `${encodedPayload}.${sign(encodedPayload)}`;
}

function readTokenAnswer(challengeId: string): string | null {
  const [encodedPayload, signature] = challengeId.split(".");
  if (!encodedPayload || !signature || !safeEqual(sign(encodedPayload), signature)) {
    return null;
  }

  try {
    const payload = JSON.parse(Buffer.from(encodedPayload, "base64url").toString("utf8")) as CaptchaTokenPayload;
    if (Date.now() - payload.issuedAt > maxTokenAgeMs) {
      return null;
    }
    return payload.answer;
  } catch {
    return null;
  }
}

export class CaptchaStore {
  private readonly answers = new Map<string, string>();
  private readonly used = new Set<string>();

  create(): CaptchaChallenge {
    const expectedAnswer = "ABCDE";
    const challengeId = createToken(expectedAnswer);
    this.answers.set(challengeId, expectedAnswer);
    return { challengeId, expectedAnswer };
  }

  verify(challengeId: string, answer: string): boolean {
    if (this.used.has(challengeId)) {
      return false;
    }
    const expected = this.answers.get(challengeId) ?? readTokenAnswer(challengeId);
    if (!expected) {
      return false;
    }
    const ok = expected.toUpperCase() === answer.trim().toUpperCase();
    if (ok) {
      this.answers.delete(challengeId);
      this.used.add(challengeId);
    }
    return ok;
  }

  renderSvg(challengeId: string): string {
    const answer = this.answers.get(challengeId) ?? readTokenAnswer(challengeId);
    if (!answer) {
      throw new Error("challenge_not_found");
    }

    return `<svg xmlns="http://www.w3.org/2000/svg" width="180" height="70" viewBox="0 0 180 70" role="img" aria-label="captcha local">
      <rect width="180" height="70" fill="#f8fafc"/>
      <path d="M0 10 L180 60 M0 30 L180 20 M20 0 L160 70 M60 0 L120 70" stroke="#b7c4d1" stroke-width="1"/>
      <text x="35" y="44" fill="#111827" font-family="monospace" font-size="25" font-weight="700" letter-spacing="5">${answer}</text>
    </svg>`;
  }
}

export const captchaStore = new CaptchaStore();
