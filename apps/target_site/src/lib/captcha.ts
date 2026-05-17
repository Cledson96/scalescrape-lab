import { randomUUID } from "node:crypto";

export type CaptchaChallenge = {
  challengeId: string;
  expectedAnswer: string;
};

export class CaptchaStore {
  private readonly answers = new Map<string, string>();

  create(): CaptchaChallenge {
    const challengeId = randomUUID();
    const expectedAnswer = "ABCDE";
    this.answers.set(challengeId, expectedAnswer);
    return { challengeId, expectedAnswer };
  }

  verify(challengeId: string, answer: string): boolean {
    const expected = this.answers.get(challengeId);
    if (!expected) {
      return false;
    }
    const ok = expected.toUpperCase() === answer.trim().toUpperCase();
    if (ok) {
      this.answers.delete(challengeId);
    }
    return ok;
  }

  renderSvg(challengeId: string): string {
    const answer = this.answers.get(challengeId);
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
