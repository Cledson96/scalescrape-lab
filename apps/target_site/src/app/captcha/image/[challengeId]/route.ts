import { NextResponse } from "next/server";

import { captchaStore } from "../../../../lib/captcha";

type RouteProps = {
  params: Promise<{ challengeId: string }>;
};

export async function GET(_request: Request, { params }: RouteProps) {
  const { challengeId } = await params;
  try {
    return new NextResponse(captchaStore.renderSvg(challengeId), {
      headers: {
        "content-type": "image/svg+xml; charset=utf-8",
        "cache-control": "no-store"
      }
    });
  } catch {
    return NextResponse.json({ detail: "challenge_not_found" }, { status: 404 });
  }
}
