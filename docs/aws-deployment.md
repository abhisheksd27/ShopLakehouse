# AWS deployment guide

**Prepared infrastructure; not applied or integration-tested in AWS.** Terraform validation checks configuration shape, not service availability, IAM completeness, runtime SQL compatibility or cost. Use ap-south-1 and review the saved plan before provisioning.

## Deployment sequence

1. Authenticate through your organization's approved short-lived AWS credentials. Confirm account/region. Create an AWS budget alert in the account; this repository does not assume free-tier eligibility.
2. Review `infra/bootstrap/main.tf`, set a globally unique state bucket name, and apply that small bootstrap stack. Preserve its local state securely. The backend uses S3 encryption/versioning and native locking.
3. Copy `infra/environments/dev/backend.hcl.example` to a private backend config, and `terraform.tfvars.example` to `terraform.tfvars`. Set the real repository and a Git SHA image tag. Leave services disabled.
4. Initialize and review:
```sh
terraform -chdir=infra/environments/dev init -backend-config=backend.hcl
terraform -chdir=infra/environments/dev plan -out=plan.tfplan
terraform -chdir=infra/environments/dev apply plan.tfplan
```
5. Configure GitHub environment variables for image role, region and ECR. Use `docker.yml` to build ARM64 application and Airflow images with cloud dependencies, scan and push immutable Git SHA tags. A HIGH/CRITICAL Trivy result blocks publication; remediate rather than bypass.
6. Run the bootstrap task:
```sh
.venv/bin/python scripts/run_ecs_task.py --environment dev --task bootstrap
```
It creates analytics/metadata databases, source migrations and initial application secrets. Secret values never enter Terraform variables/state.
7. Apply a new reviewed plan with `deploy_services=true`; wait for the private API to become healthy. Generate data and run the worker:
```sh
.venv/bin/python scripts/run_ecs_task.py --environment dev generate --day 2026-11-13 --orders 100
.venv/bin/python scripts/run_ecs_task.py --environment dev run --day 2026-11-13
```
8. Initialize Airflow with the airflow-init task, then enable `deploy_airflow` in another reviewed plan. DAGs are baked into the image. Unpause the master only after a successful manual run.
9. Resolve the published release and query its concrete Glue schema. Validate all business queries on Athena (the local SQL folder uses PostgreSQL syntax). Cloud Metabase hosting is not provisioned; connect an approved BI deployment to Athena with a read-only role and pin a published release.

## Network and identity

Dev tasks use public IPs for outbound access but security groups allow no internet ingress. RDS is private. Prod uses private tasks and NAT gateways per AZ. S3 has a gateway endpoint. API discovery is private Cloud Map DNS. Airflow UI needs an approved private access path; no public load balancer is created.

GitHub OIDC image role is restricted to the configured repository/environment. It can push images, not provision the whole infrastructure. Terraform requires a separately reviewed deployment role supplied by the operator. Reuse an existing GitHub OIDC provider when deploying multiple environments in the same account.

KMS encrypts lake, RDS and application secret; TLS is required on S3. Database connections require encryption. Before production, switch to certificate-verified TLS, dedicated source-reader/control-writer/migrator database roles, a dedicated API IAM role, private TLS for the API, and scoped BI permissions. The demo currently uses the RDS bootstrap user for runtime database access and a shared task role; this is an explicit production blocker.

## Cost planning

No dollar total is claimed without pricing and account validation. Use the AWS Pricing Calculator with ap-south-1, actual runtime hours and traffic.

| Component | Cost driver | Control |
|---|---|---|
| RDS | Instance hours, storage, backups, Multi-AZ | Small dev instance; destroy when finished |
| Fargate | vCPU/GB hours; Airflow runs continuously | Disable services outside demos; run batch tasks on demand |
| NAT gateways | Gateway hours and processed bytes | Dev avoids NAT; prod intentionally pays for private egress |
| Athena | Bytes scanned | Parquet, projection, 1 GiB query scan cutoff |
| S3 | Bytes/versions/requests | Query results expire after 14 days; set approved lake retention |
| KMS/Secrets | Keys, secrets, requests | Reuse environment-scoped resources |
| CloudWatch/CloudTrail | Log ingestion, retention, object data events | 30-day logs; monitor data-event volume |
| ECR/public IPv4 | Stored images and IP hours | Retain 20 images; stop idle services |

This stack is **not guaranteed to fit Free Tier**, especially continuously running Airflow, NAT and Multi-AZ RDS.

## Teardown

Disable scheduling and services, export needed evidence, back up source/control data and the HMAC key. Review the destroy plan. Buckets are deliberately not force-destroyed; empty versions only after approved retention review. Prod RDS requires disabling deletion protection deliberately and takes a final snapshot. Account for retained snapshots, secrets recovery windows and KMS deletion delay. Keep state storage until all stacks are gone.

## Cloud acceptance checklist

- Build and scan cloud images; prove API and CSV ingestion.
- Test Glue types, Athena dbt freshness/snapshots/merge and schema publication.
- Repeat a run and demonstrate a failed run preserves the previous release.
- Restrict runtime database/IAM roles and verify TLS certificates.
- Configure alert destination explicitly; alarms currently have no notification action.
- Prove private UI access, backup restoration and credential rotation.
- Measure duration, data scanned and actual billing before enabling daily production service.
