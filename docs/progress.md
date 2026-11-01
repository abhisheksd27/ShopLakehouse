# ShopLakehouse — Build Progress

## Objective

Build an e-commerce analytics platform locally, then validate and
deploy it on AWS.

Last updated: 2026-11-01 (Asia/Kolkata).

## Working agreement

- The user writes the application code and runs the learning commands.
- The assistant maintains this progress document as work progresses.
- Mark implementation steps verified after reviewing successful command
  output or inspecting the relevant files; instructions alone are not completion.
- Keep planned features separate from implemented features.
- Save Git commits and pushes for the end-of-day review, rather than each step.
- At the end of a workday, summarize completed work, checks, issues, and next
  steps, then provide the Git commands for the user to review and run.
- Never record passwords, tokens, or private keys in documentation.

## Progress

| Step | Task | Status |
|---|---|---|
| 1 | Docker hello-world | Verified |
| 2 | Project directory | Verified |
| 3 | Git initialized on main | Verified |
| 4 | .gitignore configured | Ignore rules verified; stray EOF line still needs removal |
| 5 | Python 3.11 virtual environment | Verified: Python 3.11.15 runs from the project .venv |
| 6 | Initial folders and progress document | Verified: folders created; Git detects docs and src |
| 7 | Initial Git commit | Verified: commit 04d9289 |
| 8 | Architecture documentation | Verified: document reviewed; committed as 2c75425 |
| 9 | Project README | Written and reviewed locally; included in the prepared end-of-day Git commands |
| 10 | Source PostgreSQL with Docker Compose | Verified: valid Compose configuration, healthy container, successful SQL connection, UTC timezone |
| 11 | Customers source table | Schema verified in PostgreSQL; insert/update smoke-test output not yet reviewed |
| 12 | Categories and products source tables | Schema and corrective migration results verified; relationship smoke-test output not yet reviewed |

## Verification evidence

- Docker successfully pulled and ran the hello-world container.
- Project directory: /Volumes/Abhishek/Data Engineering project/SHOPLAKEHOUSE.
- Python version: 3.11.15.
- Python executable: /Volumes/Abhishek/Data Engineering project/SHOPLAKEHOUSE/.venv/bin/python.
- The user created src/shoplakehouse, tests, config, scripts, data, and docs.
- src/shoplakehouse/__init__.py is tracked by Git.
- docs/architecture.md contains the project purpose, Mermaid diagram, local
  data flow, design requirements, AWS mapping, and first pipeline milestone.
- README.md contains the project overview and clearly labels the pipeline
  and AWS infrastructure as planned.
- Docker Compose configuration validates successfully.
- source-postgres is healthy, running PostgreSQL 16.15 on aarch64 and
  publishing container port 5432 at 127.0.0.1:5433.
- SQL confirmed database shoplakehouse, user shop_admin, and timezone UTC.
- No application tables existed when Step 10 was verified.
- On 2026-11-01, read-only queries verified public.customers, its identity
  primary key, required columns, check constraints, incremental index,
  case-insensitive unique email index, and updated_at trigger.
- The installed public.set_updated_at() function matches the SQL file and
  assigns clock_timestamp() to NEW.updated_at.
- The customer table currently has zero rows, including zero setup-test rows.
  This confirms its current state, not that the earlier smoke test was run.
- A later read-only check confirmed categories and products now exist with
  identity keys, indexes, and update triggers. Both tables contain zero rows.
- Before migration 003, the catalog definitions used TIMESTAMP WITHOUT TIME
  ZONE and ON DELETE CASCADE and lacked two validation checks.
- End-of-day verification on 2026-11-01 confirmed migration 003's corrections:
  all six customer/catalog timestamp columns are TIMESTAMP WITH TIME ZONE;
  products_category_id_fk uses ON DELETE RESTRICT; products_price_valid
  excludes negative values and NaN; products_stock_nonnegative is present.
- customers, categories, and products each contain zero rows. The database
  remains healthy. These read-only checks verify schema and current counts;
  they do not replace insert/update or constraint-rejection smoke tests.
- git check-ignore confirms .env and macOS sidecar files are excluded.
- End-of-day review confirmed SOURCE_DB_PASSWORD is blank in .env.example;
  the private .env is ignored and is not tracked by Git.
- Local Git metadata shows main tracking origin/main, both at 2c75425.
  The live GitHub repository was not rechecked during this update.

## Decisions

- Develop and test locally first.
- Validate AWS-specific behavior in a cloud development environment.
- Keep credentials and virtual environments out of Git.
- Update documentation after each verified step.
- Use a daily Git review and commit instead of a commit after every step.
- Customer email uniqueness is case-insensitive, implemented by the user's
  unique index on lower(email). This does not trim surrounding whitespace.

## Issues resolved

macOS metadata appeared in Git as ._.git.
Adding ._* to .gitignore excluded these files.

The missing comma after categories.updated_at was corrected in the saved
catalog SQL. The user reported completing the editor troubleshooting step;
the VS Code extension state was not independently inspected.

Migration 003 corrects catalog timestamp types, replaces cascading category
deletion with RESTRICT, and adds the missing stock and price checks. The
installed database definitions were verified after these changes.

## Open issues

The opening terminal wrapper has been removed from .gitignore, but a stray
`EOF` remains on line 19. The user should remove that line while preserving
the actual ignore patterns. Secret and metadata exclusion rules already work.

Runtime verification still pending:
- Review the customer insert/update smoke check, including the updated_at trigger.
- Review the catalog join smoke check and test rejection of invalid values.
- Schema definitions have been checked, but these runtime results have not
  been provided or independently observed.

## Step 10 — setup and verification

- Create .env.example with non-secret source database settings.
- Generate a random local password into the ignored .env file without
  printing it or overwriting an existing file.
- Create docker-compose.yml using the official postgres:16.15-bookworm image.
- Name the service source-postgres and the database shoplakehouse.
- Use shop_admin as the local bootstrap administrator; application and
  ingestion roles will be introduced separately.
- Bind the database to 127.0.0.1:5433 on the Mac, forwarding to container port 5432.
- Persist data in the source_postgres_data Docker volume mounted at
  /var/lib/postgresql/data.
- Configure a PostgreSQL readiness healthcheck and UTC server timezone.
- Verified: .env ignored by Git, Compose configuration valid, container
  healthy, SELECT current_database(), current_user successful, and server
  timezone UTC. Read-only checks were run by the assistant.
- The assistant has not created configuration files, generated credentials,
  or started containers for this step.

## Step 11 — implementation and verification

- The user created sql/source/001_customers.sql and applied it to PostgreSQL.
- public.customers has id, name, email, city, country, created_at,
  and updated_at. One row represents one customer.
- Verified an identity primary key, required fields, a unique lower(email)
  index, checks for nonblank names and uppercase two-letter country codes,
  and a timestamp-order constraint.
- Verified the (updated_at, id) index for later incremental extraction.
- Verified reusable public.set_updated_at() and the customers UPDATE trigger.
- The SQL file wraps changes in a transaction.
- Still awaiting evidence of the transaction-based insert/update smoke check.
- The assistant has not written the SQL file or created the table.

## Step 12 — implementation and verification

- The user created sql/source/002_catalog.sql and the catalog tables.
- categories: id, name, created_at, updated_at; one row per product category.
- products: id, category_id, sku, name, price, stock_quantity, created_at,
  updated_at; one row per product.
- Connect products.category_id to categories.id with a required foreign key.
- Enforce unique category names and product SKUs, nonblank names/SKUs,
  nonnegative prices and stock quantities, and valid timestamp ordering.
- Use NUMERIC(18,2) for INR product prices.
- Reuse public.set_updated_at() for both new tables.
- Add incremental-extraction indexes and a product category lookup index.
- Apply the migration, inspect the three source tables, and verify a joined
  category/product example inside a transaction that is rolled back.
- No catalog SQL or database objects have been created by the assistant.

### Corrective migration — results verified

- The user saved sql/source/003_catalog_corrections.sql; its contents and
  the resulting installed definitions were reviewed.
- The migration interprets existing timezone-free timestamps as UTC and
  converts all four catalog timestamp columns to TIMESTAMPTZ.
- products_category_id_fk now uses ON DELETE RESTRICT.
- products_price_valid excludes negative numbers and NaN;
  products_stock_nonnegative enforces stock_quantity >= 0.
- The migration wraps changes in a transaction and sets the session timezone
  locally to UTC.
- Runtime catalog smoke-check results remain pending.
- Fresh setup will apply 001, 002, and 003 in order.

## Daily log — 2026-10-31

### Completed

- Verified the local development foundation: Docker, Git, and Python 3.11.
- Established the project folders and Python package directory.
- Documented the local-first architecture and planned AWS deployment.
- Created the project README.
- Started source PostgreSQL and verified container health, database access,
  UTC timezone, and Git exclusion of .env.
- Agreed that the assistant will maintain this file and Git updates will
  happen at the end of each workday.

### Existing commits

- 04d9289: Initialize ShopLakehouse project structure and progress documentation.
- 2c75425: Document ShopLakehouse architecture and development approach.

### Pending end-of-day Git review

- Review README.md, .gitignore, .env.example, docker-compose.yml, and updates
  to this progress document. Keep .env excluded.
- Include any additional verified work completed later today.
- Create a descriptive daily commit, push it, and verify the resulting status.
- No commit or push was performed by the assistant for this progress update.

## Daily log — 2026-11-01

### Verified

- Source PostgreSQL remains healthy.
- The customers SQL file and installed table definition were inspected.
- Customer email uniqueness is case-insensitive.
- The installed update function and trigger are present; no customer rows
  or setup-test rows remain.
- Catalog tables, indexes, and update triggers exist; the saved missing comma
  is fixed. The installed timestamp types, foreign key, and price/stock checks
  now match the intended behavior after the correction migration.
- All three source tables are empty, ready for synthetic data later.

### Carry forward to the next session

- Review customer insert/update and catalog relationship smoke-check results.
- The stray EOF line in .gitignore still needs removal.
- After these checks, continue with orders and order_items.

### End-of-day Git handoff

- Prepared commit subject: feat: add local PostgreSQL and initial source schema
- Include .gitignore, .env.example, README.md, docker-compose.yml,
  docs/progress.md, and all three SQL migration files.
- Preserve the existing .env exclusion; do not stage the private .env file.
- Commands to review the staged summary, commit, push main, and verify Git
  status were supplied to the user.
- Commit and push status: awaiting user execution. The assistant has not
  staged, committed, or pushed these changes.
- Session ended at the user's request. No new implementation step was started.

## Resume point

Finish the pending customer/catalog runtime checks and remove the stray EOF
line from .gitignore. Then introduce orders and order_items. Retain the
local-first approach and daily Git review workflow.
