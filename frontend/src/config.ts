export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const SWAGGER_URL =
  import.meta.env.VITE_SWAGGER_URL ?? `${API_BASE_URL}/docs`;

export const NEO4J_BROWSER_URL =
  import.meta.env.VITE_NEO4J_BROWSER_URL ?? "http://localhost:7474";

export const PROJECT_NAME =
  import.meta.env.VITE_APP_NAME ?? "Lattice Medical Graph";

export type DocumentStatus = "uploaded" | "processing" | "completed" | "failed";

export interface StructuredPatientInfo {
  patient_id: string;
  name?: string | null;
  dob?: string | null;
  gender?: string | null;
  insurance_policy_id?: string | null;
}

export interface StructuredEncounterInfo {
  encounter_id: string;
  admission_date?: string | null;
  discharge_date?: string | null;
  visit_type?: string | null;
  department?: string | null;
}

export interface StructuredClaimInfo {
  claim_id: string;
  claim_amount?: number | null;
  approved_amount?: number | null;
  status?: string | null;
  insurer_name?: string | null;
  submission_date?: string | null;
}

export interface StructuredConditionInfo {
  condition_name: string;
  icd_code?: string | null;
  chronic?: boolean | null;
}

export interface StructuredHospitalInfo {
  hospital_id?: string | null;
  name?: string | null;
  city?: string | null;
}

export interface StructuredMedicalDocumentData {
  patient: StructuredPatientInfo;
  encounter: StructuredEncounterInfo;
  claim: StructuredClaimInfo;
  conditions: StructuredConditionInfo[];
  hospital: StructuredHospitalInfo;
}

export interface DocumentSummary {
  id: string;
  patient_id: string;
  file_name: string;
  status: DocumentStatus;
  created_at: string;
  processed_at?: string | null;
  page_count?: number | null;
  structured_data?: StructuredMedicalDocumentData | null;
}

export interface GraphNode {
  id: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphRelationship {
  source: string;
  target: string;
  type: string;
}

export interface PatientGraphResponse {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
  message?: string;
}

