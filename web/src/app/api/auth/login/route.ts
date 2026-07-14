import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { setSessionUser, upgradeLegacyPassword, verifyPassword } from "@/lib/auth";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const username = String(body?.username ?? "").trim();
  const password = String(body?.password ?? "");
  if (!username || !password) {
    return NextResponse.json({ success: false, message: "missing credentials" }, { status: 400 });
  }

  const user = await prisma.user.findFirst({ where: { username, isActive: true } });
  if (!user || !(await verifyPassword(password, user.passwordHash))) {
    return NextResponse.json({ success: false, message: "invalid login" }, { status: 401 });
  }

  await prisma.user.update({
    where: { id: user.id },
    data: { lastLoginAt: new Date() },
  });
  await upgradeLegacyPassword(user.id, password, user.passwordHash);
  await setSessionUser(user.id);

  return NextResponse.json({
    success: true,
    user: {
      id: user.id,
      username: user.username,
      role: user.role,
      storeName: user.storeName,
    },
  });
}
