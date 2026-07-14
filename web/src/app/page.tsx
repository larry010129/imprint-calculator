import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "珠寶線上訂製",
  description: "鑽石戒指／項鍊 價格試算",
};

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6 py-16">
      <p className="text-sm uppercase tracking-widest text-zinc-500">TypeScript rewrite</p>
      <h1 className="font-serif text-4xl text-zinc-900 dark:text-zinc-100">珠寶線上訂製</h1>
      <p className="text-lg text-zinc-600 dark:text-zinc-400">
        Next.js + Postgres backend is scaffolded. Core APIs (catalog, quote, submit, login) are ready.
        Shop UI and admin CMS are the next migration phases.
      </p>
      <ul className="list-disc space-y-2 pl-5 text-zinc-700 dark:text-zinc-300">
        <li>
          <a className="underline" href="/api/health">
            /api/health
          </a>
        </li>
        <li>
          <a className="underline" href="/api/catalog">
            /api/catalog
          </a>
        </li>
        <li>
          <a className="underline" href="/calculator">
            /calculator
          </a>{" "}
          (placeholder — Phase 2)
        </li>
      </ul>
      <p className="text-sm text-zinc-500">
        See <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">web/README.md</code> and{" "}
        <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">web/MIGRATION.md</code> for deploy steps.
      </p>
    </main>
  );
}
