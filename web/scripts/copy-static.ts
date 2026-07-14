import fs from "node:fs";
import path from "node:path";

const src = path.join(process.cwd(), "..", "static");
const dest = path.join(process.cwd(), "public", "static");

function copyRecursive(from: string, to: string) {
  if (!fs.existsSync(from)) {
    console.warn("Static source not found:", from);
    return;
  }
  fs.mkdirSync(to, { recursive: true });
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    const srcPath = path.join(from, entry.name);
    const destPath = path.join(to, entry.name);
    if (entry.isDirectory()) copyRecursive(srcPath, destPath);
    else fs.copyFileSync(srcPath, destPath);
  }
}

copyRecursive(src, dest);
console.log("Copied static assets to public/static");
