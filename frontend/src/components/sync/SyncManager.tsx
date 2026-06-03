import type { BankRetrieveJobStatus } from "../../types";

export function SyncProgressPanel({
    open,
    checking,
    jobStatus,
    progress,
    expectedMs,
    lastDurationSeconds,
}: {
    open: boolean;
    checking: boolean;
    jobStatus: BankRetrieveJobStatus | null;
    progress: number;
    expectedMs: number;
    lastDurationSeconds?: number | null;
}) {
    if (!open) {
        return null;
    }

    return (
        <section className="bank-retrieve-panel" aria-live="polite">
            <p className="bank-retrieve-panel-title">
                {checking
                    ? "Tjekker om hentning blev færdig i baggrunden..."
                    : jobStatus?.current_phase || "Henter seneste transaktioner fra Bank..."}
            </p>
            <div className="bank-retrieve-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
                <span className="bank-retrieve-progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <p className="bank-retrieve-panel-meta">
                Forventet tid: ca. {Math.round(expectedMs / 1000)} sek
                {lastDurationSeconds ? ` (sidst ${Math.round(lastDurationSeconds)} sek)` : ""}
            </p>
        </section>
    );
}

export function SyncActions({
    localLedger,
    saving,
    retrieving,
    checking,
    building,
    rebuildNeeded,
    pendingReviewCount,
    onBuild,
    onPrimary,
}: {
    localLedger: boolean;
    saving: boolean;
    retrieving: boolean;
    checking: boolean;
    building: boolean;
    rebuildNeeded: boolean;
    pendingReviewCount: number;
    onBuild: () => void;
    onPrimary: () => void;
}) {
    return (
        <div className="bank-spiir-filter-actions">
            {localLedger && saving ? (
                <span className="bank-save-indicator" aria-live="polite">
                    <span className="bank-saving-spinner" aria-hidden="true" />
                    Gemmer
                </span>
            ) : null}
            {localLedger ? (
                <button
                    type="button"
                    onClick={onBuild}
                    disabled={retrieving || checking || saving || building || !rebuildNeeded}
                >
                    {building ? "Bygger..." : "Byg Spiir"}
                </button>
            ) : null}
            <button
                type="button"
                onClick={onPrimary}
                disabled={retrieving || checking || saving || building}
            >
                {saving && localLedger && pendingReviewCount > 0
                    ? "Gemmer..."
                    : retrieving
                        ? "Henter..."
                        : checking
                            ? "Tjekker status..."
                            : localLedger
                                ? pendingReviewCount > 0
                                    ? "Marker gennemgået"
                                    : "Hent"
                                : "Hent seneste"}
            </button>
        </div>
    );
}
