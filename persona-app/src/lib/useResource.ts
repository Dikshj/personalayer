// Data loader with loading / error / offline states and a preview fallback.
// A network-level failure (fetch throwing, or offline) surfaces the preview
// value with `isPreview` set, so pages can render a "Backend offline" notice
// while still showing representative content.

import { useCallback, useEffect, useState } from "react";

function isNetworkError(err: unknown): boolean {
  if (typeof navigator !== "undefined" && !navigator.onLine) return true;
  if (err instanceof TypeError) return true; // fetch network failure
  const msg = err instanceof Error ? err.message.toLowerCase() : "";
  return (
    msg.includes("failed to fetch") ||
    msg.includes("networkerror") ||
    msg.includes("load failed") ||
    msg.includes("not configured")
  );
}

export interface Resource<T> {
  data: T;
  loading: boolean;
  error: string | null;
  isPreview: boolean;
  reload: () => void;
}

export function useResource<T>(loader: () => Promise<T>, preview: T, deps: unknown[] = []): Resource<T> {
  const [data, setData] = useState<T>(preview);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPreview, setIsPreview] = useState(false);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await loader();
      setData(result);
      setIsPreview(false);
    } catch (err) {
      if (isNetworkError(err)) {
        setData(preview);
        setIsPreview(true);
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong");
      }
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
  }, [run]);

  return { data, loading, error, isPreview, reload: run };
}
