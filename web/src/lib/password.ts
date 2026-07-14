import bcrypt from "bcryptjs";
import { createHash, pbkdf2Sync, timingSafeEqual } from "node:crypto";

export async function hashPassword(password: string) {
  return bcrypt.hash(password, 12);
}

/** Verify werkzeug/scrypt/pbkdf2 hashes from the Flask app, or bcrypt for new users. */
export async function verifyPassword(password: string, stored: string) {
  if (stored.startsWith("pbkdf2:") || stored.startsWith("scrypt:")) {
    return verifyWerkzeugPassword(password, stored);
  }
  return bcrypt.compare(password, stored);
}

function verifyWerkzeugPassword(password: string, stored: string) {
  const parts = stored.split("$");
  if (parts.length !== 3) return false;
  const [method, salt, hashHex] = parts;
  const [algo, digest, iterationsRaw] = method.split(":");
  const iterations = Number.parseInt(iterationsRaw ?? "0", 10);
  if (!algo || !digest || !iterations) return false;

  let derived: Buffer;
  if (algo === "pbkdf2") {
    derived = pbkdf2Sync(password, salt, iterations, 32, digest.replace("sha", "sha"));
  } else if (algo === "scrypt") {
    // werkzeug scrypt: method$salt$hash — use pbkdf2 fallback unsupported; keep login via reset
    return false;
  } else {
    return false;
  }

  const expected = Buffer.from(hashHex, "hex");
  if (expected.length !== derived.length) return false;
  return timingSafeEqual(expected, derived);
}

export function isLegacyHash(stored: string) {
  return stored.startsWith("pbkdf2:") || stored.startsWith("scrypt:");
}

export async function rehashIfLegacy(password: string, stored: string) {
  if (isLegacyHash(stored)) {
    return hashPassword(password);
  }
  return null;
}

export function sha256Hex(value: string) {
  return createHash("sha256").update(value).digest("hex");
}
