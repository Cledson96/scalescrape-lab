import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({ detail: "bloqueio simulado" }, { status: 403 });
}
