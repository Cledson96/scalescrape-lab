import {
  ANTI_BOT_HIGH_VOLUME_VISITS,
  ANTI_BOT_RATE_LIMIT_VISITS,
  ANTI_BOT_VISIT_WINDOW_MS
} from "./site-contracts";

export enum AntibotAction {
  Allow = "allow",
  Delay = "delay",
  Challenge = "challenge",
  Forbid = "forbid",
  RateLimit = "rate_limit"
}

export type AntibotDecision = {
  riskScore: number;
  action: AntibotAction;
  reason: string;
};

type Visit = {
  path: string;
  createdAt: Date;
};

type SessionState = {
  sessionId: string;
  proxyId: string;
  visits: Visit[];
  captchaErrors: number;
  sawListing: boolean;
};

type EvaluateInput = {
  sessionId: string;
  proxyId: string;
  path: string;
  userAgent: string | null;
  hasClearanceCookie: boolean;
  now?: Date;
};

export class AntibotSimulator {
  private readonly sessions = new Map<string, SessionState>();

  recordCaptchaError(sessionId: string, proxyId: string): void {
    this.getState(sessionId, proxyId).captchaErrors += 1;
  }

  evaluate(input: EvaluateInput): AntibotDecision {
    const currentTime = input.now ?? new Date();
    const state = this.getState(input.sessionId, input.proxyId);
    const oneMinuteAgo = currentTime.getTime() - ANTI_BOT_VISIT_WINDOW_MS;
    state.visits = state.visits.filter((visit) => visit.createdAt.getTime() > oneMinuteAgo);
    state.visits.push({ path: input.path, createdAt: currentTime });

    if (input.path.startsWith("/items")) {
      state.sawListing = true;
    }

    if (state.visits.length >= ANTI_BOT_RATE_LIMIT_VISITS) {
      return {
        riskScore: 95,
        action: AntibotAction.RateLimit,
        reason: "muitas requisicoes em 1 minuto"
      };
    }

    const reasons: string[] = [];
    let score = 0;

    if (state.visits.length >= ANTI_BOT_HIGH_VOLUME_VISITS) {
      score += 35;
      reasons.push("volume alto por minuto");
    }

    if (!input.hasClearanceCookie) {
      score += 20;
      reasons.push("sem cookie de sessao liberada");
    }

    if (!input.userAgent || input.userAgent.toLowerCase().includes("bot")) {
      score += 20;
      reasons.push("user-agent ausente ou suspeito");
    }

    if (input.path.startsWith("/items/") && !state.sawListing) {
      score += 25;
      reasons.push("acesso direto ao detalhe");
    }

    if (state.captchaErrors > 0) {
      score += Math.min(30, state.captchaErrors * 15);
      reasons.push("erros de captcha anteriores");
    }

    const riskScore = Math.min(score, 100);
    const reason = reasons.join(", ") || "baixo risco";

    if (riskScore < 40) {
      return { riskScore, action: AntibotAction.Allow, reason };
    }
    if (riskScore < 70) {
      return { riskScore, action: AntibotAction.Delay, reason };
    }
    if (riskScore < 90) {
      return { riskScore, action: AntibotAction.Challenge, reason };
    }
    return { riskScore, action: AntibotAction.Forbid, reason };
  }

  snapshot(): Array<SessionState & { visits: Visit[] }> {
    return Array.from(this.sessions.values()).map((state) => ({
      ...state,
      visits: [...state.visits]
    }));
  }

  private getState(sessionId: string, proxyId: string): SessionState {
    const key = `${proxyId}:${sessionId}`;
    const existing = this.sessions.get(key);
    if (existing) {
      return existing;
    }

    const state: SessionState = {
      sessionId,
      proxyId,
      visits: [],
      captchaErrors: 0,
      sawListing: false
    };
    this.sessions.set(key, state);
    return state;
  }
}

export const antibotSimulator = new AntibotSimulator();
