import type { ReactNode } from "react";

export function FilterBar({
    filters,
    stats,
    mobileReviewBar,
    pagination,
}: {
    filters: ReactNode;
    stats: ReactNode;
    mobileReviewBar?: ReactNode;
    pagination?: ReactNode;
}) {
    return (
        <section className="bank-poster-controls">
            <div className="bank-filter-bar">{filters}</div>
            {stats}
            {mobileReviewBar}
            {pagination}
        </section>
    );
}
