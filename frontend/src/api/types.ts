// Authored from the frozen Python/API contracts without importing or running the application.
export interface Profile {
  target_id:string; fixture_version:string; journey_hash:string; browser_version:string;
  browser_revision:string; viewport:[number,number]; locale:string; consent:string;
  authentication:string; service_workers:string; cache:string; collector_version:string;
  rule_version:string; identity_key_id:string; mode:string; budgets:Record<string,number>;
}
export interface StepResult { id:string; state:string; status:'REACHED'|'BLOCKED'|'NOT_RUN'; reason:string|null; started_at:string; ended_at:string }
export interface EvidenceRecord {
  id:string; kind:string; observed_at:string; step_id:string; state:string; frame_id:string;
  origin:string; url_display:string; identity:string; reference_observed:boolean;
  request_observed:boolean; response_observed:boolean; execution_evidence:'NOT_OBSERVED';
  http_status:number|null; method:string; headers:Record<string,string>; tls_validation:string;
  redirected_from:string|null; from_cache:boolean; from_service_worker:boolean;
  body_sha256:string|null; body_representation:string|null; body_size:number|null; body_reason:string|null;
  integrity_metadata:string|null; relation:string; delivery:string; limitation_codes:string[];
}
export interface Run {
  id:string; schema_version:string; label:string; fixture_id:string; profile:Profile; started_at:string;
  ended_at:string|null; status:string; provenance:string; steps:StepResult[]; evidence:EvidenceRecord[];
  frames:{id:string;origin:string;parent_id:string|null;visibility:string}[];
  limitation_codes:string[]; complete_states:string[]; is_baseline?:boolean;
}
export interface Mapping {standard:string; id:string; relationship:string; limitation:string; url:string; license?:string}
export interface Finding { id:string;rule_ids:string[];title:string;condition:string;applicability:string;evidence_sufficiency:string;confidence:string;severity:string;reason_codes:string[];evidence_ids:string[];interpretation:string;suggested_owner:string;mappings:Mapping[] }
export interface Change {kind:string;category?:string;identity:string;url_display:string;state:string;baseline_evidence_id:string|null;candidate_evidence_id:string|null;reason:string;new_origin:boolean}
export interface Comparison {baseline_id:string;candidate_id:string;eligibility:string;mismatch_fields:string[];changes:Change[];findings:Finding[]}
export interface Integrity {state:string;expected_sha256:string;actual_sha256:string|null}
export interface EvidenceDetail {schema_version:string;run_id:string;profile:Profile;provenance:string;run_status:string;integrity:Integrity;record:EvidenceRecord;preview:string;preview_truncated:boolean;preview_total_bytes:number;findings:Finding[]}
export interface RunPage {items:Run[];total:number;limit:number;offset:number;demo:boolean}
export interface RunDetail {run:Run;integrity:Integrity;findings:Finding[];demo:boolean}
export interface Journey {run_id:string;profile:Profile;steps:StepResult[];frames:Run['frames'];evidence:EvidenceRecord[];complete_states:string[];limitation_codes:string[];provenance:string}
