import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { SharedLinkAccess } from "@/api/types";

export default function SharedLinkPage() {
  const { token = "" } = useParams();
  const [data, setData] = useState<SharedLinkAccess | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await api.accessSharedLink(token);
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Share link not found",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-bgc px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-md">
        <h1 className="text-2xl text-textC">Shared item</h1>
        {loading && <p className="mt-4 text-sm text-textC">Loading…</p>}
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        {data && (
          <div className="mt-4 space-y-2 text-sm text-textC">
            <p>
              <span className="font-medium">Name:</span> {data.resource_name}
            </p>
            <p>
              <span className="font-medium">Type:</span> {data.resource_type}
            </p>
            <p>
              <span className="font-medium">Access:</span> {data.role}
            </p>
            <p className="pt-2 text-xs text-[#5f6368]">
              Sign in to open this item in your Drive if you have access.
            </p>
          </div>
        )}
        <Link
          to="/login"
          className="mt-6 inline-block rounded-full bg-[#1a73e8] px-4 py-2 text-sm font-medium text-white hover:bg-[#1558b0]"
        >
          Go to Drive
        </Link>
      </div>
    </div>
  );
}
