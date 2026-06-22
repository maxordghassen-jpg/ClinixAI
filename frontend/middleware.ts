import { NextRequest, NextResponse } from "next/server";

function getTokenRole(token: string): string | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return (payload?.role as string) ?? null;
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("clinix-token")?.value;

  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const role = getTokenRole(token);

  if (role === "doctor" && pathname.startsWith("/patient")) {
    return NextResponse.redirect(new URL("/doctor", request.url));
  }
  if (role === "patient" && pathname.startsWith("/doctor")) {
    return NextResponse.redirect(new URL("/patient", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/patient/:path*", "/doctor/:path*"],
};
