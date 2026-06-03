import { mergeUpdatedTransactions } from "./bankState";
import type {
    KvitteringerImportResponse,
    KvitteringerItemClusterDetail,
    KvitteringerItemClusterSummary,
    KvitteringerMerchantSummary,
    KvitteringerOccurrence,
    KvitteringerOverviewResponse,
    KvitteringerOverviewSunburstResponse,
    KvitteringerReceiptDetail,
    KvitteringerReceiptSummary,
    KvitteringerStatusResponse,
    BankOverridePatch,
    BankOverrideResponse,
    BankRetrieveJobStatus,
    BankRetrieveResponse,
    BankTaxonomyResponse,
    BankTransactionsResponse,
    SpiirIncomeExpenseSeriesResponse,
    SpiirOverviewResponse,
    SpiirStatusResponse,
    SpiirTransaction
} from "./types";

const API_BASE = window.location.origin.startsWith("http") ? "" : "";

let currentAccessToken = "";
export function setAccessToken(token: string) {
    currentAccessToken = token;
}

type CacheSlot<T> = {
    value: T | null;
    promise: Promise<T> | null;
};

type KvitteringerQuery = {
    dateFrom?: string;
    dateTo?: string;
    merchantKeys?: string[];
};

const spiirCache = {
    status: { value: null, promise: null } as CacheSlot<SpiirStatusResponse>,
    overview: { value: null, promise: null } as CacheSlot<SpiirOverviewResponse>,
    incomeExpenseSeries: { value: null, promise: null } as CacheSlot<SpiirIncomeExpenseSeriesResponse>,
    transactions: { value: null, promise: null } as CacheSlot<SpiirTransaction[]>
};

const localLedgerCache = {
    full: { value: null, promise: null } as CacheSlot<BankTransactionsResponse>,
    pages: new Map<string, CacheSlot<BankTransactionsResponse>>()
};

function cachedRequest<T>(slot: CacheSlot<T>, loader: () => Promise<T>): Promise<T> {
    if (slot.value !== null) {
        return Promise.resolve(slot.value);
    }
    if (slot.promise !== null) {
        return slot.promise;
    }
    slot.promise = loader()
        .then((value) => {
            slot.value = value;
            return value;
        })
        .finally(() => {
            slot.promise = null;
        });
    return slot.promise;
}

export function getCachedSpiirData(): {
    status: SpiirStatusResponse | null;
    overview: SpiirOverviewResponse | null;
    transactions: SpiirTransaction[] | null;
} {
    return {
        status: spiirCache.status.value,
        overview: spiirCache.overview.value,
        transactions: spiirCache.transactions.value
    };
}

export function invalidateSpiirCache(): void {
    spiirCache.status.value = null;
    spiirCache.status.promise = null;
    spiirCache.overview.value = null;
    spiirCache.overview.promise = null;
    spiirCache.incomeExpenseSeries.value = null;
    spiirCache.incomeExpenseSeries.promise = null;
    spiirCache.transactions.value = null;
    spiirCache.transactions.promise = null;
}

export function invalidateLocalLedgerCache(): void {
    localLedgerCache.full.value = null;
    localLedgerCache.full.promise = null;
    localLedgerCache.pages.clear();
}

function localLedgerPageKey(options?: { limit?: number; offset?: number }): string {
    return `${options?.offset ?? 0}:${options?.limit ?? "all"}`;
}

function localLedgerPageSlot(options?: { limit?: number; offset?: number }): CacheSlot<BankTransactionsResponse> {
    const key = localLedgerPageKey(options);
    const existing = localLedgerCache.pages.get(key);
    if (existing) {
        return existing;
    }
    const slot = { value: null, promise: null } as CacheSlot<BankTransactionsResponse>;
    localLedgerCache.pages.set(key, slot);
    return slot;
}

function sliceLocalLedgerResponse(payload: BankTransactionsResponse, options?: { limit?: number; offset?: number }): BankTransactionsResponse {
    const offset = Math.max(options?.offset ?? 0, 0);
    const limit = options?.limit ?? null;
    const transactions = limit === null
        ? payload.transactions.slice(offset)
        : payload.transactions.slice(offset, offset + Math.max(limit, 0));
    return {
        ...payload,
        transactions,
        loaded_count: transactions.length,
        offset,
        limit,
        has_more: offset + transactions.length < payload.transactions.length,
    };
}

function patchLocalLedgerCache(result: BankOverrideResponse): void {
    localLedgerCache.full.value = mergeUpdatedTransactions(
        localLedgerCache.full.value,
        result.updated_transactions,
        result.deleted_transaction_ids,
    );
    for (const slot of localLedgerCache.pages.values()) {
        slot.value = mergeUpdatedTransactions(slot.value, result.updated_transactions, result.deleted_transaction_ids);
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers);
    if (currentAccessToken) {
        headers.set("Authorization", `Bearer ${currentAccessToken}`);
    }

    const response = await fetch(`${API_BASE}${path}`, {
        credentials: "include",
        ...init,
        headers
    });

    if (!response.ok) {
        let message = `HTTP ${response.status} from ${path}`;
        const contentType = response.headers.get("content-type") ?? "";
        if (contentType.includes("application/json")) {
            const payload = (await response.json()) as { detail?: string };
            if (payload.detail) {
                message = payload.detail;
            }
        } else {
            const text = await response.text();
            if (text) {
                const compactText = text.replace(/\s+/g, " ").trim();
                const looksLikeHtml = /<html|<body|<title|<!doctype/i.test(compactText);
                if (looksLikeHtml) {
                    message = response.status === 504 ? `Gateway timeout (504) from ${path}` : `HTTP ${response.status} from ${path}`;
                } else {
                    message = compactText;
                }
            }
        }
        throw new Error(message);
    }

    return (await response.json()) as T;
}

function kvitteringerQueryString(query?: KvitteringerQuery & { search?: string; granularity?: "month" | "year" }): string {
    const params = new URLSearchParams();
    if (query?.granularity) {
        params.set("granularity", query.granularity);
    }
    if (query?.dateFrom) {
        params.set("date_from", query.dateFrom);
    }
    if (query?.dateTo) {
        params.set("date_to", query.dateTo);
    }
    if (query?.search?.trim()) {
        params.set("search", query.search.trim());
    }
    for (const merchantKey of query?.merchantKeys ?? []) {
        params.append("merchant_keys", merchantKey);
    }
    const serialized = params.toString();
    return serialized ? `?${serialized}` : "";
}

export async function getSpiirStatus(): Promise<SpiirStatusResponse> {
    return cachedRequest(spiirCache.status, () => request<SpiirStatusResponse>("/api/spiir/status"));
}

export async function getSpiirOverview(): Promise<SpiirOverviewResponse> {
    return cachedRequest(spiirCache.overview, () => request<SpiirOverviewResponse>("/api/spiir/overview"));
}

export async function getSpiirTransactions(): Promise<SpiirTransaction[]> {
    return cachedRequest(spiirCache.transactions, () => request<SpiirTransaction[]>("/api/spiir/transactions"));
}

export async function getSpiirIncomeExpenseSeries(): Promise<SpiirIncomeExpenseSeriesResponse> {
    return cachedRequest(spiirCache.incomeExpenseSeries, () => request<SpiirIncomeExpenseSeriesResponse>("/api/spiir/local-ledger/income-expense-series"));
}

export async function rebuildSpiirFromLocal(): Promise<{ generated_at: string; transaction_count: number; source: string }> {
    const result = await request<{ generated_at: string; transaction_count: number; source: string }>("/api/spiir/rebuild-from-local", {
        method: "POST"
    });
    invalidateSpiirCache();
    return result;
}

export async function scheduleSpiirRebuildFromLocal(delaySeconds = 10): Promise<{ scheduled: boolean; running: boolean; rebuild_required: boolean; delay_seconds?: number }> {
    return request<{ scheduled: boolean; running: boolean; rebuild_required: boolean; delay_seconds?: number }>(`/api/spiir/rebuild-from-local/schedule?delay_seconds=${delaySeconds}`, {
        method: "POST"
    });
}

export async function getBankTransactions(): Promise<BankTransactionsResponse> {
    return request<BankTransactionsResponse>("/api/bank/transactions");
}

export async function getSpiirLocalLedgerTransactions(): Promise<BankTransactionsResponse> {
    return cachedRequest(localLedgerCache.full, () => request<BankTransactionsResponse>("/api/spiir/local-ledger/transactions"));
}

export async function getSpiirLocalLedgerTransactionsPage(options?: { limit?: number; offset?: number }): Promise<BankTransactionsResponse> {
    if (options?.limit === undefined && options?.offset === undefined) {
        return getSpiirLocalLedgerTransactions();
    }
    if (localLedgerCache.full.value !== null) {
        return Promise.resolve(sliceLocalLedgerResponse(localLedgerCache.full.value, options));
    }
    const params = new URLSearchParams();
    if (options?.limit !== undefined) {
        params.set("limit", String(options.limit));
    }
    if (options?.offset !== undefined) {
        params.set("offset", String(options.offset));
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return cachedRequest(localLedgerPageSlot(options), () => request<BankTransactionsResponse>(`/api/spiir/local-ledger/transactions${suffix}`));
}

export async function saveSpiirLocalLedgerOverrides(transactionIds: string[], patch: BankOverridePatch): Promise<BankOverrideResponse> {
    const result = await request<BankOverrideResponse>("/api/spiir/local-ledger/overrides", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transaction_ids: transactionIds, patch })
    });
    patchLocalLedgerCache(result);
    return result;
}

export async function retrieveBankTransactions(): Promise<BankRetrieveResponse> {
    return request<BankRetrieveResponse>("/api/bank/retrieve", { method: "POST" });
}

export async function startBankRetrieveJob(): Promise<BankRetrieveJobStatus> {
    return request<BankRetrieveJobStatus>("/api/bank/retrieve/start", { method: "POST" });
}

export async function getBankRetrieveStatus(): Promise<BankRetrieveJobStatus> {
    return request<BankRetrieveJobStatus>("/api/bank/retrieve/status");
}

export async function syncBankIntoSpiirLocalLedger(): Promise<{
    applied_at: string;
    cutover_date: string;
    source_row_count: number;
    created_count: number;
    updated_count: number;
    autocategorized_count: number;
    skipped_before_cutover_count: number;
    skipped_missing_booking_date_count: number;
    ledger_row_count: number;
    import_run_count: number;
}> {
    const result = await request<{
        applied_at: string;
        cutover_date: string;
        source_row_count: number;
        created_count: number;
        updated_count: number;
        autocategorized_count: number;
        skipped_before_cutover_count: number;
        skipped_missing_booking_date_count: number;
        ledger_row_count: number;
        import_run_count: number;
    }>("/api/spiir/local-ledger/bank-sync/apply", { method: "POST" });
    invalidateLocalLedgerCache();
    return result;
}

export async function getBankTaxonomy(): Promise<BankTaxonomyResponse> {
    return request<BankTaxonomyResponse>("/api/bank/taxonomy");
}

export async function saveBankOverrides(transactionIds: string[], patch: BankOverridePatch): Promise<BankOverrideResponse> {
    return request<BankOverrideResponse>("/api/bank/overrides", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transaction_ids: transactionIds, patch })
    });
}

export async function getKvitteringerStatus(): Promise<KvitteringerStatusResponse> {
    return request<KvitteringerStatusResponse>("/api/kvitteringer/status");
}

export async function importKvitteringerDefault(): Promise<KvitteringerImportResponse> {
    return request<KvitteringerImportResponse>("/api/kvitteringer/import/default", {
        method: "POST"
    });
}

export async function uploadKvitteringerStoreboxJson(file: File): Promise<KvitteringerImportResponse> {
    const body = new FormData();
    body.append("file", file);
    return request<KvitteringerImportResponse>("/api/kvitteringer/import/upload", {
        method: "POST",
        body
    });
}

export async function rebuildKvitteringer(): Promise<KvitteringerImportResponse> {
    return request<KvitteringerImportResponse>("/api/kvitteringer/rebuild", {
        method: "POST"
    });
}

export async function getKvitteringerOverview(
    granularity: "month" | "year",
    query?: KvitteringerQuery
): Promise<KvitteringerOverviewResponse> {
    return request<KvitteringerOverviewResponse>(`/api/kvitteringer/overview${kvitteringerQueryString({ ...query, granularity })}`);
}

export async function getKvitteringerOverviewSunburst(
    granularity: "month" | "year",
    periods: string[],
    query?: Pick<KvitteringerQuery, "merchantKeys">
): Promise<KvitteringerOverviewSunburstResponse> {
    const params = new URLSearchParams();
    params.set("granularity", granularity);
    for (const period of periods) {
        params.append("periods", period);
    }
    for (const merchantKey of query?.merchantKeys ?? []) {
        params.append("merchant_keys", merchantKey);
    }
    return request<KvitteringerOverviewSunburstResponse>(`/api/kvitteringer/overview/sunburst?${params.toString()}`);
}

export async function getKvitteringerReceipts(query?: KvitteringerQuery): Promise<KvitteringerReceiptSummary[]> {
    return request<KvitteringerReceiptSummary[]>(`/api/kvitteringer/receipts${kvitteringerQueryString(query)}`);
}

export async function getKvitteringerReceipt(receiptId: string): Promise<KvitteringerReceiptDetail> {
    return request<KvitteringerReceiptDetail>(`/api/kvitteringer/receipts/${encodeURIComponent(receiptId)}`);
}

export async function getKvitteringerMerchants(query?: KvitteringerQuery): Promise<KvitteringerMerchantSummary[]> {
    return request<KvitteringerMerchantSummary[]>(`/api/kvitteringer/merchants${kvitteringerQueryString(query)}`);
}

export async function getKvitteringerItems(search = "", query?: KvitteringerQuery): Promise<KvitteringerItemClusterSummary[]> {
    return request<KvitteringerItemClusterSummary[]>(`/api/kvitteringer/items${kvitteringerQueryString({ ...query, search })}`);
}

export async function getKvitteringerItem(clusterId: string): Promise<KvitteringerItemClusterDetail> {
    return request<KvitteringerItemClusterDetail>(`/api/kvitteringer/items/${encodeURIComponent(clusterId)}`);
}

export async function getKvitteringerItemHistory(clusterId: string, query?: KvitteringerQuery): Promise<KvitteringerOccurrence[]> {
    return request<KvitteringerOccurrence[]>(`/api/kvitteringer/items/${encodeURIComponent(clusterId)}/history${kvitteringerQueryString(query)}`);
}

export async function getKvitteringerItemPriceHistory(clusterId: string, query?: KvitteringerQuery): Promise<KvitteringerOccurrence[]> {
    return request<KvitteringerOccurrence[]>(`/api/kvitteringer/items/${encodeURIComponent(clusterId)}/price-history${kvitteringerQueryString(query)}`);
}

export async function saveKvitteringerItemCategoryOverride(
    clusterId: string,
    categoryKey: string | null
): Promise<KvitteringerItemClusterDetail> {
    return request<KvitteringerItemClusterDetail>(`/api/kvitteringer/items/${encodeURIComponent(clusterId)}/category-override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category_key: categoryKey })
    });
}
