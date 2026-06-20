import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "wai_session";

// Edge-Runtime kann das itsdangerous-signed Cookie nicht entschluesseln —
// wir pruefen NUR Existenz. Die echte Validierung passiert Server-seitig
// im app/[slug]/layout.tsx ueber den /me-Fetch.
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Login-Seiten, statische Assets, API-Proxies und das Root-Redirect lassen wir durch
  if (
    pathname === "/login" ||
    pathname.startsWith("/login/") ||
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    pathname === "/favicon.ico" ||
    pathname === "/"
  ) {
    return NextResponse.next();
  }

  const token = req.cookies.get(SESSION_COOKIE);
  if (!token) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
