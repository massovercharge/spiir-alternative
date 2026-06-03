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
    BankTransaction,
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

let categoryLookup = new Map<string, BankTaxonomyResponse["categories"][number]>();

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

function rebuildCategoryLookup(taxonomy: BankTaxonomyResponse): BankTaxonomyResponse {
    categoryLookup = new Map(taxonomy.categories.map((category) => [String(category.categoryId), category]));
    return taxonomy;
}

function defaultCategory(categoryId: string | number | null | undefined): BankTaxonomyResponse["categories"][number] {
    return {
        categoryType: "Expense",
        mainCategoryId: "diverse",
        mainCategoryName: "Diverse",
        categoryId: categoryId || "diverse|ikke-kategoriseret",
        categoryName: "Ikke kategoriseret",
        usage_count: 0,
        search_aliases: []
    };
}

function normalizeTransaction(input: BankTransaction & { category_id?: string | null; custom_note?: string | null; is_excluded?: boolean }): BankTransaction {
    const categoryId = input.categoryId ?? input.category_id ?? null;
    const category = categoryId ? categoryLookup.get(String(categoryId)) : null;
    return {
        ...input,
        transaction_date: input.transaction_date ?? input.booking_date,
        description: input.description ?? "",
        categoryType: input.categoryType ?? category?.categoryType ?? defaultCategory(categoryId).categoryType,
        mainCategoryId: input.mainCategoryId ?? category?.mainCategoryId ?? defaultCategory(categoryId).mainCategoryId,
        mainCategoryName: input.mainCategoryName ?? category?.mainCategoryName ?? defaultCategory(categoryId).mainCategoryName,
        categoryId: input.categoryId ?? category?.categoryId ?? defaultCategory(categoryId).categoryId,
        categoryName: input.categoryName ?? category?.categoryName ?? defaultCategory(categoryId).categoryName,
        note: input.note ?? input.custom_note ?? "",
        hashtags: input.hashtags ?? [],
        pending_review: input.pending_review ?? false,
        splits: input.splits ?? [],
        source: input.source ?? "enablebanking"
    };
}

function normalizeTransactionsResponse(payload: BankTransactionsResponse): BankTransactionsResponse {
    const transactions = (payload.transactions ?? []).map(normalizeTransaction);
    const loadedCount = payload.loaded_count ?? transactions.length;
    const offset = payload.offset ?? 0;
    const transactionCount = payload.transaction_count ?? transactions.length;
    return {
        ...payload,
        accounts: payload.accounts ?? [],
        transactions,
        loaded_count: loadedCount,
        offset,
        limit: payload.limit,
        has_more: payload.has_more ?? offset + loadedCount < transactionCount,
        pending_review_count: payload.pending_review_count ?? transactions.filter((transaction) => transaction.pending_review).length,
    };
}

function normalizeOverridePatch(patch: BankOverridePatch): Record<string, unknown> {
    const next: Record<string, unknown> = { ...patch };
    if ("category" in patch) {
        next.category_id = patch.category?.categoryId ?? null;
        delete next.category;
    }
    if ("note" in patch) {
        next.custom_note = patch.note ?? "";
        delete next.note;
    }
    return next;
}

function normalizeIncomeExpenseSeries(payload: any): SpiirIncomeExpenseSeriesResponse {
    if (Array.isArray(payload?.months) && Array.isArray(payload?.periods)) {
        return payload as SpiirIncomeExpenseSeriesResponse;
    }
    const months = (payload?.series ?? []).map((month: any) => ({
        month: String(month.month),
        income: Number(month.income ?? 0),
        expense: Math.abs(Number(month.expense ?? 0)),
        net: Number(month.net ?? 0),
        is_current_month: String(month.month) === new Date().toISOString().slice(0, 7),
        source: payload?.source ?? "v2"
    }));
    const monthKeys = months.map((month: SpiirIncomeExpenseSeriesResponse["months"][number]) => month.month);
    const years = Array.from(new Set(monthKeys.map((month: string) => Number(month.slice(0, 4)))))
        .filter((year): year is number => Number.isFinite(year));
    return {
        generated_at: payload?.generated_at ?? new Date().toISOString(),
        source: payload?.source ?? "v2",
        months,
        years,
        periods: [
            {
                label: "12 mdr.",
                totals_title: "Seneste 12 måneder",
                start_month: monthKeys.slice(-12)[0] ?? "",
                end_month: monthKeys[monthKeys.length - 1] ?? "",
                months: monthKeys.slice(-12),
            },
            {
                label: "Alle",
                totals_title: "Hele perioden",
                start_month: monthKeys[0] ?? "",
                end_month: monthKeys[monthKeys.length - 1] ?? "",
                months: monthKeys,
            }
        ]
    };
}

function toSpiirTransaction(transaction: BankTransaction): SpiirTransaction {
    const ymd = transaction.booking_date || transaction.transaction_date || "";
    return {
        yyyymm: ymd.slice(0, 7),
        year: ymd.slice(0, 4),
        ymd,
        amount: transaction.amount,
        categoryType: transaction.categoryType,
        mainCategoryName: transaction.mainCategoryName,
        categoryName: transaction.categoryName,
        categoryId: transaction.categoryId,
        mainCategoryId: transaction.mainCategoryId,
        description: transaction.description,
        comment: transaction.note,
        hashtags: transaction.hashtags ?? [],
    };
}

function buildOverviewSection(transactions: SpiirTransaction[], periodOf: (transaction: SpiirTransaction) => string): SpiirOverviewResponse["monthly"] {
    const periods = [...new Set(transactions.map(periodOf).filter(Boolean))].sort();
    const rowsByKey = new Map<string, SpiirOverviewResponse["monthly"]["rows"][number]>();

    function touchRow(key: string, label: string, level: number, parent: string | null, transaction: SpiirTransaction): SpiirOverviewResponse["monthly"]["rows"][number] {
        const existing = rowsByKey.get(key);
        if (existing) {
            return existing;
        }
        const row = {
            key,
            label,
            level,
            parent,
            values: {},
            total: 0,
            avg: 0,
            kind: transaction.categoryType,
            categoryType: transaction.categoryType,
            mainCategoryName: transaction.mainCategoryName,
            mainCategoryId: transaction.mainCategoryId,
            categoryName: level > 1 ? transaction.categoryName : null,
            categoryId: level > 1 ? transaction.categoryId : null,
            hashtag: null,
        };
        rowsByKey.set(key, row);
        return row;
    }

    for (const transaction of transactions) {
        const period = periodOf(transaction);
        if (!period) {
            continue;
        }
        const main = transaction.mainCategoryName || "Diverse";
        const category = transaction.categoryName || "Ikke kategoriseret";
        const mainKey = `main:${transaction.categoryType ?? "Expense"}:${main}`;
        const subKey = `${mainKey}:${category}`;
        for (const row of [
            touchRow(mainKey, main, 1, null, transaction),
            touchRow(subKey, category, 2, mainKey, transaction),
        ]) {
            row.values[period] = Number(row.values[period] ?? 0) + transaction.amount;
            row.total += transaction.amount;
        }
    }

    const rows = [...rowsByKey.values()].map((row) => ({
        ...row,
        total: Math.round(row.total * 100) / 100,
        avg: periods.length ? Math.round((row.total / periods.length) * 100) / 100 : 0,
    }));
    return { periods, rows };
}

function buildSpiirOverview(transactions: SpiirTransaction[]): SpiirOverviewResponse {
    return {
        generated_at: new Date().toISOString(),
        monthly: buildOverviewSection(transactions, (transaction) => transaction.yyyymm),
        yearly: buildOverviewSection(transactions, (transaction) => transaction.year),
        shopping_extras: {
            unknownTop: [],
            suspects: [],
        },
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
    return cachedRequest(spiirCache.status, async () => {
        const transactions = await request<BankTransactionsResponse>("/api/transactions?limit=1");
        return {
            raw_exists: true,
            processed_exists: true,
            raw_file: "",
            processed_dir: "",
            generated_at: transactions.generated_at ?? null,
            transaction_count: transactions.transaction_count,
            rebuild_required: false,
        };
    });
}

export async function getSpiirOverview(): Promise<SpiirOverviewResponse> {
    return cachedRequest(spiirCache.overview, async () => buildSpiirOverview(await getSpiirTransactions()));
}

export async function getSpiirTransactions(): Promise<SpiirTransaction[]> {
    return cachedRequest(spiirCache.transactions, async () => {
        const response = normalizeTransactionsResponse(await request<BankTransactionsResponse>("/api/transactions"));
        return response.transactions.map(toSpiirTransaction);
    });
}

export async function getSpiirIncomeExpenseSeries(): Promise<SpiirIncomeExpenseSeriesResponse> {
    return cachedRequest(spiirCache.incomeExpenseSeries, async () => normalizeIncomeExpenseSeries(await request("/api/insights/income-expense-series")));
}

export async function rebuildSpiirFromLocal(): Promise<{ generated_at: string; transaction_count: number; source: string }> {
    invalidateSpiirCache();
    const response = await request<BankTransactionsResponse>("/api/transactions?limit=1");
    return {
        generated_at: response.generated_at ?? new Date().toISOString(),
        transaction_count: response.transaction_count,
        source: "v2",
    };
}

export async function scheduleSpiirRebuildFromLocal(delaySeconds = 10): Promise<{ scheduled: boolean; running: boolean; rebuild_required: boolean; delay_seconds?: number }> {
    invalidateSpiirCache();
    return { scheduled: true, running: false, rebuild_required: false, delay_seconds: delaySeconds };
}

export async function getBankTransactions(): Promise<BankTransactionsResponse> {
    return normalizeTransactionsResponse(await request<BankTransactionsResponse>("/api/transactions"));
}

export async function getSpiirLocalLedgerTransactions(): Promise<BankTransactionsResponse> {
    return cachedRequest(localLedgerCache.full, async () => normalizeTransactionsResponse(await request<BankTransactionsResponse>("/api/transactions")));
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
    return cachedRequest(localLedgerPageSlot(options), async () => normalizeTransactionsResponse(await request<BankTransactionsResponse>(`/api/transactions${suffix}`)));
}

export async function saveSpiirLocalLedgerOverrides(transactionIds: string[], patch: BankOverridePatch): Promise<BankOverrideResponse> {
    const result = await request<BankOverrideResponse>("/api/transactions", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transaction_ids: transactionIds, patch: normalizeOverridePatch(patch) })
    });
    patchLocalLedgerCache(result);
    return result;
}

export async function retrieveBankTransactions(): Promise<BankRetrieveResponse> {
    const status = await startBankRetrieveJob();
    return {
        retrieved_count: status.result?.retrieved_count ?? 0,
        transaction_count: status.result?.transaction_count ?? 0,
        raw_files: [],
        last_retrieved_at: status.completed_at ?? status.started_at ?? null,
    };
}

export async function startBankRetrieveJob(): Promise<BankRetrieveJobStatus> {
    return request<BankRetrieveJobStatus>("/api/sync/start", { method: "POST" });
}

export async function getBankRetrieveStatus(): Promise<BankRetrieveJobStatus> {
    return request<BankRetrieveJobStatus>("/api/sync/status");
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
    invalidateLocalLedgerCache();
    const response = await request<BankTransactionsResponse>("/api/transactions?limit=1");
    return {
        applied_at: response.generated_at ?? new Date().toISOString(),
        cutover_date: "",
        source_row_count: response.transaction_count,
        created_count: 0,
        updated_count: 0,
        autocategorized_count: 0,
        skipped_before_cutover_count: 0,
        skipped_missing_booking_date_count: 0,
        ledger_row_count: response.transaction_count,
        import_run_count: 0,
    };
}

export async function getBankTaxonomy(): Promise<BankTaxonomyResponse> {
    return rebuildCategoryLookup(await request<BankTaxonomyResponse>("/api/categories"));
}

export async function saveBankOverrides(transactionIds: string[], patch: BankOverridePatch): Promise<BankOverrideResponse> {
    return request<BankOverrideResponse>("/api/transactions", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transaction_ids: transactionIds, patch: normalizeOverridePatch(patch) })
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
