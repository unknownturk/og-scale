// Der Browser spricht nie direkt mit dem Backend. Diese Route hängt das
// gemeinsame Geheimnis an; die Anmeldung prüft proxy.ts davor.
import { NextResponse } from "next/server";

async function forward(request: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const base = process.env.BACKEND_URL;
  const key = process.env.BACKEND_API_KEY;
  if (!base || !key) return NextResponse.json({ detail: "Backend ist nicht eingerichtet" }, { status: 503 });
  const { path } = await ctx.params;
  const url = `${base.replace(/\/$/, "")}/${path.map(encodeURIComponent).join("/")}${new URL(request.url).search}`;
  const hasBody = !["GET", "HEAD"].includes(request.method);
  try {
    const res = await fetch(url, {
      method: request.method,
      headers: { "X-API-Key": key, "Content-Type": "application/json" },
      body: hasBody ? await request.text() : undefined,
      cache: "no-store",
    });
    return new NextResponse(res.status === 204 ? null : await res.text(), {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Das Backend ist nicht erreichbar" }, { status: 502 });
  }
}

export { forward as GET, forward as POST, forward as PATCH, forward as DELETE };
