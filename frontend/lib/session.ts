// Anmelde-Cookie: "<ablauf>.<signatur>", signiert mit AUTH_SECRET (HMAC-SHA256).
export const COOKIE = "ogs_session";
const DAYS = 30;

async function sign(value: string): Promise<string> {
  const secret = process.env.AUTH_SECRET || "";
  if (secret.length < 16) throw new Error("AUTH_SECRET fehlt oder ist zu kurz");
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value));
  return Array.from(new Uint8Array(mac)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function createSession(): Promise<{ value: string; maxAge: number }> {
  const maxAge = DAYS * 24 * 60 * 60;
  const expires = String(Math.floor(Date.now() / 1000) + maxAge);
  return { value: `${expires}.${await sign(expires)}`, maxAge };
}

export async function validSession(value: string | undefined): Promise<boolean> {
  if (!value) return false;
  const [expires, mac] = value.split(".");
  if (!expires || !mac || Number(expires) < Date.now() / 1000) return false;
  try {
    return safeEqual(mac, await sign(expires));
  } catch {
    return false;
  }
}
