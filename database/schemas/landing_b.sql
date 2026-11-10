CREATE SCHEMA IF NOT EXISTS landing_b;

CREATE TABLE landing_b.received_records (
  received_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  batch_reference TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  source_record_key TEXT,
  raw_payload JSONB NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processing_status TEXT NOT NULL DEFAULT 'pendiente',
  validation_errors JSONB NOT NULL DEFAULT '[]'::JSONB,

  CONSTRAINT chk_received_records_entity_type
    CHECK (
      entity_type IN (
        'customers',
        'credit_accounts',
        'payments',
        'account_balances'
      )
    ),

  CONSTRAINT chk_received_records_processing_status
    CHECK (processing_status IN ('pendiente', 'aceptado', 'rechazado')),

  CONSTRAINT chk_received_records_validation_errors_array
    CHECK (jsonb_typeof(validation_errors) = 'array')
);
