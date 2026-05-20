import { NextRequest, NextResponse } from "next/server";

import { isPublicTargetPath } from "./lib/auth";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (isPublicTargetPath(pathname) || request.cookies.get("lab_auth")?.value === "ok") {
    return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.search = "";
  loginUrl.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!.*\\..*).*)", "/favicon.ico"]
};
