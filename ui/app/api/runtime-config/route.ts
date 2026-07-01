import { headers } from "next/headers";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const host = (await headers()).get("host")?.split(":")[0] ?? "127.0.0.1";
  return NextResponse.json({
    apiUrl:
      process.env.MAYAJAL_API_URL ??
      process.env.NEXT_PUBLIC_API_URL ??
      "http://" + host + ":8001",
  });
}
