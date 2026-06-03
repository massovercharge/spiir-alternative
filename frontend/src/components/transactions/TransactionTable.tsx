import type { RefObject, ReactNode } from "react";

import type { BankCategoryOption, BankTransaction } from "../../types";

export type TransactionSortKey = "booking_date" | "description" | "category" | "amount";
export type TransactionSortDirection = "asc" | "desc";

export type TransactionTableRow = {
    rowId: string;
    parentId: string;
    transaction: BankTransaction;
    splitId: string | null;
    splitIndex: number | null;
    isSplitChild: boolean;
    amount: number;
    note: string;
    category: BankCategoryOption;
};

function SortHeader({
    label,
    sortKey,
    activeSortKey,
    direction,
    onSort
}: {
    label: string;
    sortKey: TransactionSortKey;
    activeSortKey: TransactionSortKey;
    direction: TransactionSortDirection;
    onSort: (sortKey: TransactionSortKey) => void;
}) {
    const active = sortKey === activeSortKey;
    return (
        <button type="button" className={active ? "bank-sort-header active" : "bank-sort-header"} onClick={() => onSort(sortKey)}>
            <span>{label}</span>
            <span aria-hidden="true">{active ? (direction === "asc" ? "▲" : "▼") : ""}</span>
        </button>
    );
}

function RowMarker({ label, children }: { label: string; children: ReactNode }) {
    return (
        <span className="bank-row-marker" title={label} aria-label={label}>
            {children}
        </span>
    );
}

export function TransactionTable({
    tableContainerRef,
    visibleTransactions,
    selectedIds,
    allVisibleSelected,
    visibleRowIds,
    loading,
    filteredTransactionCount,
    categoryCount,
    sortKey,
    sortDirection,
    onSort,
    onSelectAll,
    onSelectRow,
    onToggleRow,
    renderCategoryPicker,
    detailTitle,
    rowClassName,
    formatDate,
    formatAmount,
    isPendingReview,
    isUncategorized,
    categoryLabel,
}: {
    tableContainerRef: RefObject<HTMLDivElement>;
    visibleTransactions: TransactionTableRow[];
    selectedIds: string[];
    allVisibleSelected: boolean;
    visibleRowIds: string[];
    loading: boolean;
    filteredTransactionCount: number;
    categoryCount: number;
    sortKey: TransactionSortKey;
    sortDirection: TransactionSortDirection;
    onSort: (sortKey: TransactionSortKey) => void;
    onSelectAll: (checked: boolean) => void;
    onSelectRow: (rowId: string, modifiers?: { metaKey?: boolean; shiftKey?: boolean }) => void;
    onToggleRow: (rowId: string, checked: boolean, shiftKey: boolean) => void;
    renderCategoryPicker: (row: TransactionTableRow) => ReactNode;
    detailTitle: (transaction: BankTransaction) => string;
    rowClassName: (row: TransactionTableRow, selected: boolean, selectedCount: number) => string | undefined;
    formatDate: (value: string) => string;
    formatAmount: (value: number) => string;
    isPendingReview: (transaction: BankTransaction) => boolean;
    isUncategorized: (category: BankCategoryOption) => boolean;
    categoryLabel: (row: TransactionTableRow) => string;
}) {
    return (
        <div className="bank-posting-table-container" ref={tableContainerRef}>
            <table className="bank-table">
                <colgroup>
                    <col className="bank-checkbox-column" />
                    <col className="bank-date-column" />
                    <col className="bank-description-column" />
                    <col className="bank-category-column" />
                    <col className="bank-icon-column" />
                    <col className="bank-icon-column" />
                    <col className="bank-amount-column" />
                </colgroup>
                <thead>
                    <tr>
                        <th className="bank-checkbox-cell">
                            <input
                                type="checkbox"
                                checked={allVisibleSelected}
                                onClick={(event) => event.stopPropagation()}
                                onChange={() => onSelectAll(!allVisibleSelected)}
                            />
                        </th>
                        <th className="bank-date-cell"><SortHeader label="Dato" sortKey="booking_date" activeSortKey={sortKey} direction={sortDirection} onSort={onSort} /></th>
                        <th><SortHeader label="Beskrivelse" sortKey="description" activeSortKey={sortKey} direction={sortDirection} onSort={onSort} /></th>
                        <th><SortHeader label="Kategori" sortKey="category" activeSortKey={sortKey} direction={sortDirection} onSort={onSort} /></th>
                        <th className="bank-icon-cell" />
                        <th className="bank-icon-cell" />
                        <th><SortHeader label="Beløb" sortKey="amount" activeSortKey={sortKey} direction={sortDirection} onSort={onSort} /></th>
                    </tr>
                </thead>
                <tbody>
                    {visibleTransactions.map((row) => {
                        const selected = selectedIds.includes(row.rowId);
                        const note = row.note.trim();
                        const pending = isPendingReview(row.transaction);
                        const uncategorized = isUncategorized(row.category);
                        return (
                            <tr
                                key={row.rowId}
                                data-row-id={row.rowId}
                                title={detailTitle(row.transaction)}
                                className={rowClassName(row, selected, selectedIds.length)}
                                onClick={(event) => {
                                    if (event.metaKey || event.shiftKey) {
                                        event.preventDefault();
                                    }
                                    onSelectRow(row.rowId, { metaKey: event.metaKey, shiftKey: event.shiftKey });
                                }}
                            >
                                <td className="bank-checkbox-cell" onClick={(event) => event.stopPropagation()}>
                                    <input type="checkbox" checked={selected} onChange={(event) => onToggleRow(row.rowId, event.target.checked, (event.nativeEvent as MouseEvent).shiftKey)} />
                                </td>
                                <td className="bank-date-cell">{formatDate(row.transaction.booking_date)}</td>
                                <td className="bank-description-cell">
                                    <span>{row.transaction.description}</span>
                                    {note ? <span className="bank-description-note"> ({note})</span> : null}
                                    {pending ? <span className="bank-pending-pill">Pending</span> : null}
                                </td>
                                <td className="bank-category-cell" onClick={selected ? (event) => event.stopPropagation() : undefined}>
                                    <div className="bank-category-wrapper">
                                        {selected && selectedIds.length === 1 && categoryCount > 0 ? (
                                            renderCategoryPicker(row)
                                        ) : (
                                            <span className={uncategorized ? "bank-category-text bank-category-text-empty" : "bank-category-text"}>{uncategorized ? "" : categoryLabel(row)}</span>
                                        )}
                                    </div>
                                </td>
                                <td className="bank-icon-cell">{row.isSplitChild ? <RowMarker label="Split">S</RowMarker> : null}</td>
                                <td className="bank-icon-cell">{row.transaction.is_extraordinary ? <RowMarker label="Ekstraordinær">E</RowMarker> : null}</td>
                                <td className={row.amount < 0 ? "spiir-negative bank-amount-cell" : row.amount > 0 ? "spiir-positive bank-amount-cell" : "spiir-neutral bank-amount-cell"}>
                                    {formatAmount(row.amount)}
                                </td>
                            </tr>
                        );
                    })}
                    {!loading && filteredTransactionCount === 0 ? (
                        <tr>
                            <td colSpan={7}>Ingen Bank-transaktioner matcher filteret.</td>
                        </tr>
                    ) : null}
                </tbody>
            </table>
        </div>
    );
}
