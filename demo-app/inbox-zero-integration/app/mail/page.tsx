/**
 * MODIFIED inbox-zero mail page — PersonaLayer integration.
 *
 * Replaces: apps/web/app/(app)/[emailAccountId]/mail/page.tsx
 *
 * Changes vs original:
 *   1. Import usePersonaLayer hook
 *   2. Call hook — get viewConfig (layout, sort fn)
 *   3. Sort allThreads with persona-aware comparator
 *   4. Pass viewConfig to <List> so it renders the right layout
 *   5. <PersonaLayerBanner> mounted above the list
 *
 * The original file is 100% unchanged in logic — we only wrap it
 * with persona-awareness. If PersonaLayer is offline, everything
 * falls back to the original behavior.
 */

"use client";

import { useCallback, useEffect, use } from "react";
import useSWRInfinite from "swr/infinite";
import { useSetAtom } from "jotai";
import { List } from "@/components/email-list/EmailList";
import { LoadingContent } from "@/components/LoadingContent";
import type { ThreadsQuery } from "@/utils/threads/validation";
import type { ThreadsResponse } from "@/app/api/threads/route";
import { refetchEmailListAtom } from "@/store/email";
import { BetaBanner } from "@/app/(app)/[emailAccountId]/mail/BetaBanner";
import { ClientOnly } from "@/components/ClientOnly";
import { PermissionsCheck } from "@/app/(app)/[emailAccountId]/PermissionsCheck";

// ── PersonaLayer additions ──
import { usePersonaLayer } from "@/hooks/usePersonaLayer";
import { PersonaLayerBanner } from "@/components/email-list/PersonaLayerBanner";

export default function Mail(props: {
  searchParams: Promise<{ type?: string; labelId?: string }>;
}) {
  const searchParams = use(props.searchParams);

  // ── PersonaLayer: fetch user persona before render ──
  const { viewConfig } = usePersonaLayer();

  const getKey = (
    pageIndex: number,
    previousPageData: ThreadsResponse | null,
  ) => {
    if (previousPageData && !previousPageData.nextPageToken) return null;
    const query: ThreadsQuery = {};
    if (searchParams.type === "label" && searchParams.labelId) {
      query.labelId = searchParams.labelId;
    } else if (searchParams.type) {
      query.type = searchParams.type;
    }
    if (pageIndex > 0 && previousPageData?.nextPageToken) {
      query.nextPageToken = previousPageData.nextPageToken;
    }
    // biome-ignore lint/suspicious/noExplicitAny: external shape
    const queryParams = new URLSearchParams(query as any);
    return `/api/threads?${queryParams.toString()}`;
  };

  const { data, size, setSize, isLoading, error, mutate } =
    useSWRInfinite<ThreadsResponse>(getKey, {
      keepPreviousData: true,
      dedupingInterval: 1000,
      revalidateOnFocus: false,
    });

  // ── PersonaLayer: sort threads before rendering ──
  const rawThreads = data ? data.flatMap((page) => page.threads) : [];
  const allThreads = viewConfig.sortThreads(rawThreads);

  const isLoadingMore =
    isLoading || (size > 0 && data && typeof data[size - 1] === "undefined");
  const showLoadMore = data ? !!data[data.length - 1]?.nextPageToken : false;

  const refetch = useCallback(
    (options?: { removedThreadIds?: string[] }) => {
      mutate(
        (currentData) => {
          if (!currentData) return currentData;
          if (!options?.removedThreadIds) return currentData;
          return currentData.map((page) => ({
            ...page,
            threads: page.threads.filter(
              (t) => !options?.removedThreadIds?.includes(t.id),
            ),
          }));
        },
        { rollbackOnError: true, populateCache: true, revalidate: false },
      );
    },
    [mutate],
  );

  const setRefetchEmailList = useSetAtom(refetchEmailListAtom);
  useEffect(() => {
    setRefetchEmailList({ refetch });
  }, [refetch, setRefetchEmailList]);

  const handleLoadMore = useCallback(() => {
    setSize((size) => size + 1);
  }, [setSize]);

  return (
    <>
      <PermissionsCheck />
      <ClientOnly>
        <BetaBanner />
      </ClientOnly>

      {/* ── PersonaLayer: render persona banner ── */}
      <ClientOnly>
        <PersonaLayerBanner />
      </ClientOnly>

      <LoadingContent loading={isLoading && !data} error={error}>
        {allThreads && (
          <List
            emails={allThreads}
            refetch={refetch}
            type={searchParams.type}
            showLoadMore={showLoadMore}
            handleLoadMore={handleLoadMore}
            isLoadingMore={isLoadingMore}
            /* ── PersonaLayer: pass view config ── */
            viewConfig={viewConfig}
          />
        )}
      </LoadingContent>
    </>
  );
}
