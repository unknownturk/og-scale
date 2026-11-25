import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { COOKIE, validSession } from "./lib/session";

export async function proxy(request: NextRequest) {
  if (await validSession(request.cookies.get(COOKIE)?.value)) return NextResponse.next();
  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "Nicht angemeldet" }, { status: 401 });
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: ["/((?!login|api/login|_next/static|_next/image|favicon.ico).*)"],
};
