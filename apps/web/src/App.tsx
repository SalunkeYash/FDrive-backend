import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  service?: string;
};

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetch("/health")
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<HealthResponse>;
      })
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "API unreachable");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <h1 className="text-xl font-semibold tracking-tight">FDrive</h1>
          <span className="text-sm text-stone-500">Phase 01 · Foundation</span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-16">
        <p className="max-w-xl text-lg text-stone-600">
          Your files, organized. Project foundation is up — API, web shell, and
          local infrastructure are ready for Phase 02.
        </p>

        <div className="mt-10 rounded-lg border border-stone-200 bg-white p-6">
          <h2 className="text-sm font-medium uppercase tracking-wide text-stone-500">
            API status
          </h2>
          {error && (
            <p className="mt-3 text-sm text-red-700">
              {error}
              <span className="mt-1 block text-stone-500">
                Start the API:{" "}
                <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs">
                  cd apps/api && uvicorn app.main:app --reload
                </code>
              </span>
            </p>
          )}
          {health && !error && (
            <p className="mt-3 text-sm text-emerald-800">
              {health.service ?? "api"} · {health.status}
            </p>
          )}
          {!health && !error && (
            <p className="mt-3 text-sm text-stone-400">Checking…</p>
          )}
        </div>
      </main>
    </div>
  );
}
