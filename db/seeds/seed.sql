-- Claim Cruncher Dev Seed Data
-- ALL DATA IS FAKE — no real PHI

-- Organizations
INSERT INTO organizations (id, name, slug, address, phone, email, npi) VALUES
('a0000000-0000-0000-0000-000000000001', 'Brazelton Medical Billing', 'brazelton-billing', '123 Main St, Hazel Green, AL 35750', '256-555-0100', 'admin@brazeltonbilling.com', '1234567890'),
('a0000000-0000-0000-0000-000000000002', 'Valley Health Partners', 'valley-health', '456 Oak Ave, Huntsville, AL 35801', '256-555-0200', 'info@valleyhealth.com', '0987654321');

-- Users (passwords are all "ClaimCruncher2026!" hashed with argon2)
-- For dev seeding, we use a bcrypt placeholder since argon2 needs runtime hashing
-- The auth service will handle real hashing — these are for schema testing
INSERT INTO users (id, organization_id, email, password_hash, first_name, last_name, role, phone) VALUES
-- Brazelton Billing users
('b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'gavin@brazeltonbilling.com', '$argon2id$v=19$m=65536,t=3,p=4$SEEDHASH_REPLACE_AT_RUNTIME', 'Gavin', 'Brazelton', 'org_admin', '256-555-0101'),
('b0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'sarah@brazeltonbilling.com', '$argon2id$v=19$m=65536,t=3,p=4$SEEDHASH_REPLACE_AT_RUNTIME', 'Sarah', 'Mitchell', 'biller', '256-555-0102'),
('b0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'mike@brazeltonbilling.com', '$argon2id$v=19$m=65536,t=3,p=4$SEEDHASH_REPLACE_AT_RUNTIME', 'Mike', 'Johnson', 'coder', '256-555-0103'),
('b0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'audit@brazeltonbilling.com', '$argon2id$v=19$m=65536,t=3,p=4$SEEDHASH_REPLACE_AT_RUNTIME', 'Lisa', 'Chen', 'auditor', NULL),
-- Valley Health users
('b0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000002', 'admin@valleyhealth.com', '$argon2id$v=19$m=65536,t=3,p=4$SEEDHASH_REPLACE_AT_RUNTIME', 'Tom', 'Williams', 'org_admin', '256-555-0201'),
('b0000000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000002', 'client@valleyhealth.com', '$argon2id$v=19$m=65536,t=3,p=4$SEEDHASH_REPLACE_AT_RUNTIME', 'Rachel', 'Davis', 'client', '256-555-0202'),
-- Super admin (no org)
('b0000000-0000-0000-0000-000000000099', NULL, 'shane@claimcruncher.dev', '$argon2id$v=19$m=65536,t=3,p=4$SEEDHASH_REPLACE_AT_RUNTIME', 'Shane', 'Brazelton', 'super_admin', '256-555-0001');

-- Facilities
INSERT INTO facilities (id, organization_id, name, facility_type, address, city, state, zip, phone, npi, tax_id) VALUES
('c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Huntsville Regional Medical Center', 'hospital', '100 Hospital Dr', 'Huntsville', 'AL', '35801', '256-555-1001', '1112223333', '62-1234567'),
('c0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'Madison Family Clinic', 'clinic', '200 Clinic Rd', 'Madison', 'AL', '35758', '256-555-1002', '4445556666', '62-7654321'),
('c0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Decatur Skilled Nursing', 'snf', '300 Care Ln', 'Decatur', 'AL', '35601', '256-555-1003', '7778889999', '62-1111111'),
('c0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000002', 'Valley Urgent Care', 'clinic', '400 Valley Blvd', 'Huntsville', 'AL', '35802', '256-555-1004', '3334445555', '62-2222222');

-- Facility Assignments
INSERT INTO facility_assignments (facility_id, user_id, role, is_primary) VALUES
('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'biller', TRUE),
('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'coder', TRUE),
('c0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000002', 'biller', TRUE),
('c0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000003', 'coder', FALSE),
('c0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000002', 'biller', TRUE);

-- Patients (FAKE PHI — generated names)
INSERT INTO patients (id, organization_id, first_name, last_name, date_of_birth, mrn, gender, primary_insurance_name, primary_insurance_id) VALUES
('d0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'John', 'Smith', '1985-03-15', 'MRN-10001', 'male', 'Blue Cross Blue Shield AL', 'BCBS-AA-123456'),
('d0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'Maria', 'Garcia', '1972-11-28', 'MRN-10002', 'female', 'Aetna', 'AET-BB-789012'),
('d0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Robert', 'Taylor', '1990-07-04', 'MRN-10003', 'male', 'UnitedHealthcare', 'UHC-CC-345678'),
('d0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'Emily', 'Wilson', '1968-01-20', 'MRN-10004', 'female', 'Medicare', 'MCR-DD-901234'),
('d0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000002', 'James', 'Anderson', '1995-09-12', 'MRN-20001', 'male', 'Cigna', 'CIG-EE-567890');

-- Claims
INSERT INTO claims (id, organization_id, facility_id, patient_id, claim_number, form_type, status, date_of_service_from, date_of_service_to, total_charges, provider_npi, assigned_coder_id, assigned_biller_id, submitted_by_id) VALUES
('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'CLM-2026-0001', 'cms_1500', 'ready_for_review', '2026-04-01', '2026-04-01', 1250.00, '1112223333', 'b0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000001'),
('e0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000002', 'd0000000-0000-0000-0000-000000000002', 'CLM-2026-0002', 'cms_1500', 'in_progress', '2026-04-03', '2026-04-03', 350.00, '4445556666', 'b0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000001'),
('e0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000003', 'CLM-2026-0003', 'ub_04', 'submitted', '2026-04-05', '2026-04-07', 8750.00, '1112223333', NULL, NULL, 'b0000000-0000-0000-0000-000000000001'),
('e0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000003', 'd0000000-0000-0000-0000-000000000004', 'CLM-2026-0004', 'cms_1500', 'denied', '2026-03-15', '2026-03-15', 475.00, '7778889999', 'b0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000001'),
('e0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'CLM-2026-0005', 'cms_1500', 'paid', '2026-03-01', '2026-03-01', 200.00, '1112223333', 'b0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000001');

-- Claim Lines
INSERT INTO claim_lines (claim_id, line_number, cpt_code, cpt_description, icd_codes, units, charge_amount, date_of_service) VALUES
('e0000000-0000-0000-0000-000000000001', 1, '99214', 'Office visit, established patient, moderate', ARRAY['J06.9', 'R05.9'], 1, 250.00, '2026-04-01'),
('e0000000-0000-0000-0000-000000000001', 2, '87804', 'Rapid strep test', ARRAY['J02.9'], 1, 45.00, '2026-04-01'),
('e0000000-0000-0000-0000-000000000001', 3, '96372', 'Therapeutic injection', ARRAY['J06.9'], 1, 85.00, '2026-04-01'),
('e0000000-0000-0000-0000-000000000002', 1, '99213', 'Office visit, established patient, low', ARRAY['M54.5'], 1, 175.00, '2026-04-03'),
('e0000000-0000-0000-0000-000000000002', 2, '97110', 'Therapeutic exercises', ARRAY['M54.5'], 2, 175.00, '2026-04-03'),
('e0000000-0000-0000-0000-000000000005', 1, '99212', 'Office visit, established patient, straightforward', ARRAY['Z00.00'], 1, 200.00, '2026-03-01');

-- Tickets
INSERT INTO tickets (id, organization_id, claim_id, title, description, ticket_type, status, priority, assigned_to_id, created_by_id, due_date) VALUES
('f0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000004', 'Appeal denied claim CLM-2026-0004', 'Medicare denied for missing modifier. Need to resubmit with modifier 25.', 'denial_appeal', 'open', 1, 'b0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000003', '2026-04-15'),
('f0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000003', 'Code UB-04 for inpatient stay', 'Three-day inpatient, need DRG assignment and all procedure codes.', 'coding_review', 'open', 2, 'b0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000001', '2026-04-12'),
('f0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', NULL, 'Dr. Martinez license expiring', 'State license expires May 15 — need renewal docs.', 'credential_issue', 'open', 2, 'b0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000004', '2026-05-01');

-- Ticket Comments
INSERT INTO ticket_comments (ticket_id, author_id, body, is_internal) VALUES
('f0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'Checked the original claim — modifier 25 was missing on the E&M code. Preparing corrected claim.', TRUE),
('f0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'Filing appeal with corrected CMS-1500 today.', FALSE);

-- Credentials
INSERT INTO credentials (id, organization_id, facility_id, provider_name, credential_type, credential_number, issuing_state, issued_date, expiry_date, status) VALUES
('70000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'Dr. Carlos Martinez', 'state_license', 'AL-MD-98765', 'AL', '2024-05-15', '2026-05-15', 'expiring_soon'),
('70000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'Dr. Carlos Martinez', 'npi', '1112223333', NULL, '2020-01-01', NULL, 'active'),
('70000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'Dr. Carlos Martinez', 'dea', 'AM1234567', 'AL', '2025-01-01', '2027-01-01', 'active'),
('70000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000004', 'Dr. Angela Park', 'state_license', 'AL-MD-11111', 'AL', '2025-06-01', '2027-06-01', 'active'),
('70000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000004', 'Dr. Angela Park', 'npi', '3334445555', NULL, '2019-03-15', NULL, 'active');

-- Credential Alerts (Dr. Martinez license expiring soon)
INSERT INTO credential_alerts (credential_id, alert_type, alert_date) VALUES
('70000000-0000-0000-0000-000000000001', '90_day_warning', '2026-02-15'),
('70000000-0000-0000-0000-000000000001', '60_day_warning', '2026-03-15'),
('70000000-0000-0000-0000-000000000001', '30_day_warning', '2026-04-15');
