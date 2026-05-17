import { NextResponse } from "next/server";

import { antibotSimulator } from "../../../../lib/antibot";

export function GET() {
  return NextResponse.json(
    antibotSimulator.snapshot().map((session) => ({
      session_id: session.sessionId,
      proxy_id: session.proxyId,
      captcha_errors: session.captchaErrors,
      saw_listing: session.sawListing,
      visits: session.visits.map((visit) => ({
        path: visit.path,
        created_at: visit.createdAt.toISOString()
      }))
    }))
  );
}
