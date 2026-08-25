/**
 * Peng API Client — Unified Barrel Module
 *
 * Decomposed into modular domain modules:
 * - http: HTTP client, token management, and headers
 * - types: TypeScript domain models and interfaces
 * - domains/transactions: Transaction fetching, tagging, splits, and categorization
 * - domains/accounts: Account management, banking, and sync
 * - domains/budgets: Budgets, bills, and annual summary
 * - domains/categories: Categories and recurring rules
 * - domains/insights: Time series, averages, and sunburst charts
 * - domains/households: Multi-tenant household management and invitations
 * - domains/rules: Categorization rules engine
 * - domains/inbound: Storebox receipts and inbound email ingestion
 */

export * from './http';
export * from './types';
export * from './domains/transactions';
export * from './domains/accounts';
export * from './domains/budgets';
export * from './domains/categories';
export * from './domains/insights';
export * from './domains/households';
export * from './domains/rules';
export * from './domains/inbound';
