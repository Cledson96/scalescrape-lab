import { NextResponse } from "next/server";

import { normalizeNextPath, validateLoginCredentials } from "../../../lib/auth";
import { captchaStore } from "../../../lib/captcha";

export async function POST(request: Request) {
  const form = await request.formData();
  const username = String(form.get("username") ?? "");
  const password = String(form.get("password") ?? "");
  const captchaAnswer = String(form.get("captcha_answer") ?? "");
  const challengeId = String(form.get("challenge_id") ?? "");
  const nextPath = normalizeNextPath(String(form.get("next") ?? ""));

  const credentialsOk = validateLoginCredentials(username, password);
  const captchaOk = captchaStore.verify(challengeId, captchaAnswer);

  if (!credentialsOk || !captchaOk) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", nextPath);
    loginUrl.searchParams.set("error", "invalid");
    return NextResponse.redirect(loginUrl, { status: 303 });
  }

  const response = NextResponse.redirect(new URL(nextPath, request.url), { status: 303 });
  response.cookies.set("lab_auth", "ok", {
    httpOnly: true,
    path: "/",
    sameSite: "lax"
  });
  response.cookies.set("lab_clearance", "ok", {
    httpOnly: true,
    path: "/",
    sameSite: "lax"
  });
  return response;
}
