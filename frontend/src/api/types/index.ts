export interface SuggestedReceiptItem {
  name: string;
  amount_minor: number;
  quantity?: number;
}

export interface SuggestedReceipt {
  receipt_id: string;
  merchant_name: string;
  merchant_key: string;
  purchase_date: string;
  purchase_timestamp: string;
  total_price_minor: number;
  currency: string;
  confidence: 'high' | 'medium' | 'suggested';
  date_diff_days?: number | null;
  is_exact_amount: boolean;
  is_merchant_match: boolean;
  items_preview: SuggestedReceiptItem[];
}

export interface Account {
  uid: string;
  name: string;
  iban: string | null;
  currency: string;
  source: string;
  account_type: string;
  savings_category_id?: string | null;
  balance: string;
  balance_minor: number;
  bank_connection: {
    id: string;
    provider: string;
    bank_name: string;
    status: string;
  } | null;
}

export interface InboundEmailLog {
  id: string;
  household_id: string;
  received_at: string;
  sender: string;
  recipient?: string | null;
  subject?: string | null;
  status: 'success' | 'failed' | 'pending' | 'no_link' | string;
  download_url?: string | null;
  error_message?: string | null;
  raw_receipt_count: number;
  deduplicated_receipt_count: number;
  auto_linked_count: number;
  source_type: string;
}

export interface ImportRun {
  id: number;
  started_at: string;
  completed_at?: string | null;
  status: string;
  source_path?: string;
  source_type?: string;
  notes?: string | null;
  source_file_count: number;
  deduplicated_receipt_count: number;
}

export interface ReceiptsStatus {
  source_dir: string;
  database_path: string;
  database_exists: boolean;
  source_file_count: number;
  receipt_count: number;
  matched_receipt_count: number;
  matched_transaction_count: number;
  match_rate_percent: number;
  merchant_count: number;
  item_cluster_count: number;
  sources: {
    storebox: number;
    coop: number;
  };
  last_import_run?: ImportRun | null;
  recent_import_runs: ImportRun[];
}

export interface InboundConfig {
  household_id: string;
  household_name: string;
  inbound_token: string;
  email_address: string;
  domain: string;
  prefix: string;
  imap_enabled: boolean;
}

export interface BudgetBill {
  id?: string;
  name: string;
  amount_minor: number;
  months: number[];
  interval_type?: string;
  note?: string;
}

export interface BudgetSummaryCategory {
  category_id: string;
  category_name?: string;
  main_category_name?: string;
  category_type: string;
  expense_type: string;
  total_budgeted_minor: number;
  total_actual_minor: number;
  months: {
    month: number;
    budgeted_minor: number;
    actual_minor: number;
    difference_minor: number;
  }[];
}

export interface BudgetsSummary {
  year: number;
  categories: BudgetSummaryCategory[];
  total_income_budgeted_minor: number;
  total_income_actual_minor: number;
  total_expense_budgeted_minor: number;
  total_expense_actual_minor: number;
}
