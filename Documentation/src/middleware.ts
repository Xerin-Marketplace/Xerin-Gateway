import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const authPresent = request.cookies.get("xerin_auth_present")?.value === "1";
  const adminPresent = request.cookies.get("xerin_admin_present")?.value === "1";
  const sellerPresent = request.cookies.get("xerin_seller_present")?.value === "1";

  if (pathname.startsWith("/admin")) {
    if (!adminPresent) {
      const signinUrl = new URL("/signin", request.url);
      signinUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(signinUrl);
    }
  }

  if (pathname.startsWith("/seller/dashboard")) {
    if (!sellerPresent && !adminPresent) {
      const signinUrl = new URL("/signin", request.url);
      signinUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(signinUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*", "/seller/dashboard/:path*"],
};
