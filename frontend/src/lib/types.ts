export interface Voyage {
  id: string;
  vessel_name: string;
  voyage_number: string;
  counterparty?: string | null;
  sw_user?: string | null;
  load_port?: string | null;
  discharge_port?: string | null;
  terminal?: string | null;
  berth?: string | null;
  country?: string | null;
  operation_type: string;
  laycan_from?: string | null;
  laycan_to?: string | null;
  allowed_laytime_value: string;
  allowed_laytime_unit: string;
  demurrage_rate_type: string;
  demurrage_rate_value: string;
  currency: string;
  nor_allowance_hours: string;
  workflow_state: string;
  comments?: string | null;
  created_at: string;
}

export interface SOFEvent {
  id: string;
  port_call_id: string;
  category: string;
  subtype?: string | null;
  start_time: string;
  end_time?: string | null;
  source_text?: string | null;
  document_id?: string | null;
  page_number?: number | null;
  confidence_score?: number | null;
  confidence_status: string;
  status: string;
  comment?: string | null;
}

export interface AtomicIntervalOut {
  interval_start: string;
  interval_end: string;
  duration_seconds: number;
  active_event_ids: string[];
  matched_rule_ids: string[];
  primary_rule_id: string;
  primary_rule_name: string;
  secondary_rule_ids: string[];
  final_time_count_factor: string;
  final_demurrage_rate_factor: string;
  decision_reason: string;
}

export interface CalculationVersion {
  id: string;
  voyage_id: string;
  version_no: number;
  kind: string;
  rule_set_version_id: string;
  results: {
    commencement: {
      candidates: { label: string; time: string | null; rule_id: string }[];
      selected: string;
      selected_label: string;
      rule_applied: string;
    };
    intervals: AtomicIntervalOut[];
    integrity: { ok: boolean; error: string | null; detail: string | null };
    laytime: {
      gross_elapsed_seconds: number;
      used_laytime_seconds: number;
      remaining_laytime_seconds: number;
      excess_time_seconds: number;
      demurrage_commencement: string | null;
    };
    demurrage: {
      full_rate_time_seconds: number;
      half_rate_time_seconds: number;
      other_rate_time_seconds: number;
      daily_rate: string;
      amount: string;
    };
  };
  integrity_ok: boolean;
  status: string;
  created_at: string;
}

export interface ExplanationResult {
  interval: AtomicIntervalOut;
  sof_evidence: {
    id: string;
    category: string;
    start_time: string;
    end_time: string | null;
    source_text: string | null;
    document_id: string | null;
    page_number: number | null;
  }[];
  selected_rule: {
    id: string;
    name: string;
    rule_definition_code: string;
    time_count_factor: number;
    demurrage_rate_factor: number;
    scope: string;
    source_document_id: string | null;
    source_clause_id: string | null;
    source_page: number | null;
    source_note: string | null;
  } | null;
  secondary_rules: ExplanationResult["selected_rule"][];
  decision_reason: string;
}

export interface DocumentOut {
  id: string;
  voyage_id: string;
  type: string;
  filename: string;
  mime_type?: string | null;
  page_count?: number | null;
  extraction_method?: string | null;
  status: string;
  uploaded_at: string;
}
