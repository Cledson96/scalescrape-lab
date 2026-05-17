import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({ detail: "rate limit simulado" }, { status: 429 });
}
