CREATE SCHEMA IF NOT EXISTS source_b;

CREATE TYPE source_b.account_status_type AS ENUM (
  'activo',
  'inactivo',
  'bloqueado',
  'cancelado'
);

CREATE TYPE source_b.payment_status_type AS ENUM (
  'pendiente',
  'aplicado',
  'rechazado',
  'reversado'
);

CREATE TABLE source_b.customers (
  customer_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_type TEXT NOT NULL,
  document_number TEXT NOT NULL,

  CONSTRAINT uq_customers_document
    UNIQUE (document_type, document_number)
);

CREATE TABLE source_b.credit_accounts (
  credit_account_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_business_key TEXT NOT NULL,
  customer_id INTEGER NOT NULL,
  product_type TEXT NOT NULL,
  opening_date DATE NOT NULL,
  account_status source_b.account_status_type NOT NULL,

  CONSTRAINT uq_credit_accounts_business_key
    UNIQUE (account_business_key),

  CONSTRAINT fk_credit_accounts_customer
    FOREIGN KEY (customer_id)
    REFERENCES source_b.customers (customer_id)
);

CREATE TABLE source_b.payments (
  payment_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  payment_business_key TEXT NOT NULL,
  credit_account_id INTEGER NOT NULL,
  payment_date DATE NOT NULL,
  payment_amount NUMERIC(15, 2) NOT NULL,
  payment_status source_b.payment_status_type NOT NULL,

  CONSTRAINT uq_payments_business_key
    UNIQUE (payment_business_key),

  CONSTRAINT chk_payments_positive_amount
    CHECK (payment_amount > 0),

  CONSTRAINT fk_payment_accounts
    FOREIGN KEY (credit_account_id)
    REFERENCES source_b.credit_accounts (credit_account_id)
);

CREATE TABLE source_b.account_balances (
  credit_account_id INTEGER NOT NULL,
  cutoff_date DATE NOT NULL,
  principal_balance NUMERIC(15, 2) NOT NULL,
  interest_balance NUMERIC(15, 2) NOT NULL,
  fees_balance NUMERIC(15, 2) NOT NULL,
  total_balance NUMERIC(15, 2) NOT NULL,
  currency TEXT NOT NULL,

  CONSTRAINT pk_account_balances
    PRIMARY KEY (credit_account_id, cutoff_date),

  CONSTRAINT fk_account_balances_credit_account
    FOREIGN KEY (credit_account_id)
    REFERENCES source_b.credit_accounts (credit_account_id)
);
