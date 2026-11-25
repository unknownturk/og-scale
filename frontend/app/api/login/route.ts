import { NextResponse } from "next/server";
import { COOKIE, createSession, safeEqual } from "@/lib/session";

export async function POST(request: Request) {
  const expected = process.env.APP_PASSWORD || "";
  if (!expected) return NextResponse.json({ detail: "APP_PASSWORD ist nicht gesetzt" }, { status: 503 });
  const { password } = await request.json().catch(() => ({ password: "" }));
  if (typeof password !== "string" || !safeEqual(password, expected)) {
    await new Promise((r) => setTimeout(r, 600)); // bremst Rateversuche
    return NextResponse.json({ detail: "Das Passwort stimmt nicht" }, { status: 401 });
  }
  const session = await createSession();
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE, session.value, {
    httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: session.maxAge,
  });
  return res;
}
