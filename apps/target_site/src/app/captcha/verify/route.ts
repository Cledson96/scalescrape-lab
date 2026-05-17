import { NextResponse } from "next/server";

import { antibotSimulator } from "../../../lib/antibot";
import { captchaStore } from "../../../lib/captcha";

export async function POST(request: Request) {
  const contentType = request.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await request.json()
    : Object.fromEntries(await request.formData());

  const challengeId = String(payload.challenge_id ?? payload.challengeId ?? "");
  const answer = String(payload.answer ?? "");
  const sessionId = String(payload.session_id ?? payload.sessionId ?? "anonymous");
  const proxyId = String(payload.proxy_id ?? payload.proxyId ?? "direct");
  const ok = captchaStore.verify(challengeId, answer);
  const response = NextResponse.json({ ok });

  if (ok) {
    response.cookies.set("lab_clearance", "ok", {
      httpOnly: true,
      path: "/",
      sameSite: "lax"
    });
  } else {
    antibotSimulator.recordCaptchaError(sessionId, proxyId);
  }

  return response;
}
