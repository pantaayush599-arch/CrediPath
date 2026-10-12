-- CrediPath schema (generated from app/models.py). Run in the Supabase SQL editor if you prefer
-- to create tables manually; the API also creates them automatically on startup.

CREATE TABLE businesses (
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	owner_name VARCHAR(160) NOT NULL, 
	category VARCHAR(80) NOT NULL, 
	city VARCHAR(120) NOT NULL, 
	years_in_operation INTEGER, 
	description TEXT NOT NULL, 
	bureau_status VARCHAR(60) NOT NULL, 
	conventional_view TEXT NOT NULL, 
	is_synthetic BOOLEAN NOT NULL, 
	is_seeded BOOLEAN NOT NULL, 
	consent_given_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE action_progress (
	id SERIAL NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	action_key VARCHAR(40) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	note TEXT, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_progress_action UNIQUE (business_id, action_key), 
	CONSTRAINT ck_progress_status CHECK (status IN ('pending','in_progress','completed')), 
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);
CREATE INDEX ix_action_progress_business_id ON action_progress (business_id);

CREATE TABLE uploads (
	id SERIAL NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	rows_total INTEGER NOT NULL, 
	rows_inserted INTEGER NOT NULL, 
	rows_updated INTEGER NOT NULL, 
	rows_duplicate INTEGER NOT NULL, 
	rows_rejected INTEGER NOT NULL, 
	report JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE
);
CREATE INDEX ix_uploads_business_id ON uploads (business_id);

CREATE TABLE assessments (
	id SERIAL NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	trigger VARCHAR(20) NOT NULL, 
	upload_id INTEGER, 
	scoring_version VARCHAR(20) NOT NULL, 
	as_of_date DATE NOT NULL, 
	window_start DATE NOT NULL, 
	window_end DATE NOT NULL, 
	overall_score FLOAT, 
	display_score INTEGER, 
	confidence VARCHAR(10) NOT NULL, 
	confidence_reasons JSON NOT NULL, 
	record_count INTEGER NOT NULL, 
	summary JSON NOT NULL, 
	monthly JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
	FOREIGN KEY(upload_id) REFERENCES uploads (id) ON DELETE SET NULL
);
CREATE INDEX ix_assessments_business_created ON assessments (business_id, id);

CREATE TABLE financial_records (
	id SERIAL NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	upload_id INTEGER, 
	record_type VARCHAR(20) NOT NULL, 
	date DATE NOT NULL, 
	amount FLOAT NOT NULL, 
	direction VARCHAR(10), 
	counterparty VARCHAR(160), 
	category VARCHAR(40), 
	channel VARCHAR(40), 
	reference VARCHAR(80), 
	due_date DATE, 
	paid_date DATE, 
	balance_after FLOAT, 
	notes TEXT, 
	fingerprint VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_record_fingerprint UNIQUE (business_id, fingerprint), 
	CONSTRAINT ck_amount_positive CHECK (amount > 0), 
	CONSTRAINT ck_record_type CHECK (record_type IN ('bank','sale','invoice','supplier_payment','loan_repayment')), 
	FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
	FOREIGN KEY(upload_id) REFERENCES uploads (id) ON DELETE SET NULL
);
CREATE INDEX ix_records_business_type_date ON financial_records (business_id, record_type, date);

CREATE TABLE indicator_scores (
	id SERIAL NOT NULL, 
	assessment_id INTEGER NOT NULL, 
	position INTEGER NOT NULL, 
	key VARCHAR(40) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	weight FLOAT NOT NULL, 
	effective_weight FLOAT NOT NULL, 
	sub_score FLOAT, 
	contribution FLOAT, 
	status VARCHAR(20) NOT NULL, 
	band VARCHAR(20) NOT NULL, 
	metric FLOAT, 
	metric_label VARCHAR(160) NOT NULL, 
	benchmark FLOAT NOT NULL, 
	explanation_banker TEXT NOT NULL, 
	explanation_merchant TEXT NOT NULL, 
	details JSON NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_indicator_per_assessment UNIQUE (assessment_id, key), 
	CONSTRAINT ck_sub_score_range CHECK (sub_score IS NULL OR (sub_score >= 0 AND sub_score <= 100)), 
	FOREIGN KEY(assessment_id) REFERENCES assessments (id) ON DELETE CASCADE
);
CREATE INDEX ix_indicator_scores_assessment_id ON indicator_scores (assessment_id);

CREATE TABLE recommendations (
	id SERIAL NOT NULL, 
	assessment_id INTEGER NOT NULL, 
	rank INTEGER NOT NULL, 
	action_key VARCHAR(40) NOT NULL, 
	indicator_key VARCHAR(40) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	short_label VARCHAR(30) NOT NULL, 
	why TEXT NOT NULL, 
	steps JSON NOT NULL, 
	current_sub_score FLOAT NOT NULL, 
	target_sub_score FLOAT NOT NULL, 
	expected_impact FLOAT NOT NULL, 
	in_top_plan BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assessment_id) REFERENCES assessments (id) ON DELETE CASCADE
);
CREATE INDEX ix_recommendations_assessment_id ON recommendations (assessment_id);

CREATE TABLE risk_flags (
	id SERIAL NOT NULL, 
	assessment_id INTEGER NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	category VARCHAR(20) NOT NULL, 
	severity VARCHAR(10) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	detail TEXT NOT NULL, 
	requires_verification BOOLEAN NOT NULL, 
	evidence JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assessment_id) REFERENCES assessments (id) ON DELETE CASCADE
);
CREATE INDEX ix_risk_flags_assessment_id ON risk_flags (assessment_id);

