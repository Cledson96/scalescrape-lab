import { createHmac, randomInt, randomUUID, timingSafeEqual } from "node:crypto";

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
const captchaAlphabet = "23456789HJKLMNPQRSTUVWXYZ";

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

function createAnswer(): string {
  const fixedAnswer = process.env.TARGET_SITE_FIXED_CAPTCHA_ANSWER?.trim().toUpperCase();
  if (fixedAnswer) {
    return fixedAnswer;
  }

  return Array.from({ length: 5 }, () => captchaAlphabet[randomInt(captchaAlphabet.length)]).join("");
}

function escapeSvgText(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;");
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
    const expectedAnswer = createAnswer();
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
    const safeAnswer = escapeSvgText(answer);
    const letters = safeAnswer
      .split("")
      .map((letter, index) => {
        const x = 30 + index * 24;
        const y = 43 + (index % 2 === 0 ? -2 : 3);
        const rotation = [-8, 6, -4, 9, -6][index] ?? 0;
        return `<text x="${x}" y="${y}" transform="rotate(${rotation} ${x} ${y})">${letter}</text>`;
      })
      .join("");

    return `<svg xmlns="http://www.w3.org/2000/svg" width="180" height="70" viewBox="0 0 180 70" role="img" aria-label="captcha local">
      <defs>
        <filter id="roughen">
          <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" seed="7"/>
          <feDisplacementMap in="SourceGraphic" scale="1.8"/>
        </filter>
      </defs>
      <rect width="180" height="70" fill="#f8fafc"/>
      <path d="M0 10 L180 60 M0 30 L180 20 M20 0 L160 70 M60 0 L120 70" stroke="#b7c4d1" stroke-width="1"/>
      <path d="M8 48 C36 28 70 60 102 36 S150 30 172 48" fill="none" stroke="#0f766e" stroke-width="2" opacity="0.55"/>
      <g fill="#111827" font-family="monospace" font-size="25" font-weight="700" filter="url(#roughen)">
        ${letters}
      </g>
      <g fill="#0f172a" opacity="0.26">
        <circle cx="18" cy="22" r="1.7"/>
        <circle cx="152" cy="18" r="1.3"/>
        <circle cx="118" cy="54" r="1.5"/>
        <circle cx="68" cy="17" r="1.1"/>
      </g>
    </svg>`;
  }
}

export const captchaStore = new CaptchaStore();
