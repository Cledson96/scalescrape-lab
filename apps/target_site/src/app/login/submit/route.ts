import { NextResponse } from "next/server";

import { normalizeNextPath, validateLoginCredentials } from "../../../lib/auth";
import { verifyRecaptcha } from "../../../lib/recaptcha";

function redirectTarget(request: Request, path: string): URL {
  const fallbackUrl = new URL(request.url);
  const forwardedProto = request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim();
  const proto = forwardedProto || fallbackUrl.protocol.replace(":", "") || "http";
  const forwardedHost = request.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const host = forwardedHost || request.headers.get("host") || fallbackUrl.host;
  return new URL(path, `${proto}://${host}`);
}

export async function POST(request: Request) {
  const form = await request.formData();
  const username = String(form.get("username") ?? "");
  const password = String(form.get("password") ?? "");
  const recaptchaToken = String(form.get("g-recaptcha-response") ?? "");
  const nextPath = normalizeNextPath(String(form.get("next") ?? ""));

  const credentialsOk = validateLoginCredentials(username, password);
  const captchaOk = await verifyRecaptcha(recaptchaToken);

  if (!credentialsOk || !captchaOk) {
    const loginUrl = redirectTarget(request, "/login");
    loginUrl.searchParams.set("next", nextPath);
    loginUrl.searchParams.set("error", "invalid");
    return NextResponse.redirect(loginUrl, { status: 303 });
  }

  const response = NextResponse.redirect(redirectTarget(request, nextPath), { status: 303 });
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

