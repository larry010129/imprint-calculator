import { cookies } from "next/headers";
import { prisma } from "@/lib/db";
import {
  hashPassword as hashPasswordInternal,
  rehashIfLegacy,
  verifyPassword as verifyPasswordInternal,
} from "@/lib/password";

export const SESSION_COOKIE = "imprint_session";

export type SessionUser = {
  id: number;
  username: string;
  role: string;
  storeName: string | null;
};

export const hashPassword = hashPasswordInternal;
export const verifyPassword = verifyPasswordInternal;

export async function getSessionUser(): Promise<SessionUser | null> {
  const cookieStore = await cookies();
  const raw = cookieStore.get(SESSION_COOKIE)?.value;
  if (!raw) return null;
  const id = Number.parseInt(raw, 10);
  if (!Number.isFinite(id)) return null;
  const user = await prisma.user.findFirst({
    where: { id, isActive: true },
    select: { id: true, username: true, role: true, storeName: true },
  });
  return user;
}

export async function setSessionUser(userId: number) {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, String(userId), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 14,
  });
}

export async function clearSessionUser() {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE);
}

export async function requireUser() {
  const user = await getSessionUser();
  if (!user) throw new Error("unauthorized");
  return user;
}

export async function requireAdmin() {
  const user = await requireUser();
  if (user.role !== "admin") throw new Error("forbidden");
  return user;
}

export async function upgradeLegacyPassword(userId: number, password: string, storedHash: string) {
  const nextHash = await rehashIfLegacy(password, storedHash);
  if (nextHash) {
    await prisma.user.update({ where: { id: userId }, data: { passwordHash: nextHash } });
  }
}
