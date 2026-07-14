export default function CalculatorPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="mb-4 font-serif text-3xl">品項試算</h1>
      <p className="mb-6 text-zinc-600 dark:text-zinc-400">
        Phase 2 will port the shop UI here. APIs are already available at{" "}
        <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">/api/catalog</code> and{" "}
        <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">/api/quote</code>.
      </p>
      <p className="text-sm text-zinc-500">
        Until then, keep using the Flask calculator or point{" "}
        <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">script.js</code> fetch URLs to this
        host.
      </p>
    </main>
  );
}
