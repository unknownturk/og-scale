// Der Browser spricht nie direkt mit dem Backend. Diese Route hängt das
// gemeinsame Geheimnis an; die Anmeldung prüft proxy.ts davor.
// Inhalte gehen unverändert durch — auch Bilder und Datei-Uploads.
import { NextResponse } from "next/server";

async function forward(request: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const base = process.env.BACKEND_URL;
  const key = process.env.BACKEND_API_KEY;
  if (!base || !key) return NextResponse.json({ detail: "Backend ist nicht eingerichtet" }, { status: 503 });
  const { path } = await ctx.params;
  const url = `${base.replace(/\/$/, "")}/${path.map(encodeURIComponent).join("/")}${new URL(request.url).search}`;
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const headers: Record<string, string> = { "X-API-Key": key };
  const type = request.headers.get("content-type");
  if (hasBody) headers["Content-Type"] = type || "application/json";
  try {
    const res = await fetch(url, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    });
    const out = new Headers({ "Content-Type": res.headers.get("Content-Type") || "application/json" });
    const cache = res.headers.get("Cache-Control");
    if (cache) out.set("Cache-Control", cache);
    return new NextResponse(res.status === 204 ? null : await res.arrayBuffer(), { status: res.status, headers: out });
  } catch {
    return NextResponse.json({ detail: "Das Backend ist nicht erreichbar" }, { status: 502 });
  }
}

export { forward as GET, forward as POST, forward as PATCH, forward as DELETE };
