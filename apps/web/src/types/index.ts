export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Facility {
  id: string;
  organization_id: string;
  name: string;
  facility_type: string;
  npi: string | null;
  tax_id: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  phone: string | null;
  fax: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Patient {
  id: string;
  organization_id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  mrn: string | null;
  insurance_provider: string | null;
  insurance_id: string | null;
  created_at: string;
}

export type ClaimStatus =
  | 'submitted'
  | 'ocr_processing'
  | 'ocr_failed'
  | 'ready_for_review'
  | 'in_progress'
  | 'coded'
  | 'billed'
  | 'paid'
  | 'denied'
  | 'appealed'
  | 'void';

export interface ClaimLine {
  id: string;
  claim_id: string;
  line_number: number;
  cpt_code: string | null;
  cpt_description: string | null;
  icd_codes: string[];
  units: number;
  charge_amount: string;
  allowed_amount: string | null;
  paid_amount: string | null;
  date_of_service: string | null;
}

export interface Claim {
  id: string;
  organization_id: string;
  claim_number: string;
  patient_id: string;
  patient?: Patient;
  facility_id: string;
  facility?: Facility;
  status: ClaimStatus;
  date_of_service: string;
  date_of_service_end: string | null;
  total_charges: string;
  total_allowed: string | null;
  total_paid: string | null;
  assigned_coder_id: string | null;
  assigned_coder?: User | null;
  assigned_biller_id: string | null;
  assigned_biller?: User | null;
  primary_icd_code: string | null;
  notes: string | null;
  claim_lines?: ClaimLine[];
  created_at: string;
  updated_at: string;
}

export interface Ticket {
  id: string;
  organization_id: string;
  claim_id: string | null;
  title: string;
  description: string | null;
  ticket_type: string;
  status: string;
  priority: string;
  assigned_to_id: string | null;
  assigned_to?: User | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface Credential {
  id: string;
  organization_id: string;
  provider_name: string;
  credential_type: string;
  credential_number: string;
  issuing_authority: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  status: string;
  notes: string | null;
  created_at: string;
}
