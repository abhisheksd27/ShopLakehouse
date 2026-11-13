# Infrastructure

This code creates paid AWS resources. It has not been applied by the assistant.
Read ../docs/aws-deployment.md before using it.

1. Bootstrap an encrypted, versioned state bucket with infra/bootstrap.
2. Copy an environment's backend.hcl.example to a local backend.hcl and use
   terraform init -backend-config=backend.hcl.
3. Review a saved plan before apply. Services default off until images and
   secrets are ready.
4. Dev avoids NAT gateways by placing tasks with public IPs in public subnets;
   security groups allow no internet-originated inbound connections. RDS stays
   private. Prod uses private tasks and a NAT gateway per availability zone.
5. Buckets are not force-destroyed. Prod RDS has deletion protection and a
   final snapshot. State bucket deletion is protected.

GitHub image-push federation is scoped to the repository/environment. Terraform
apply requires a separate operator-reviewed infrastructure role; the image role
cannot provision infrastructure. Reuse the OIDC provider ARN when deploying a
second environment in the same AWS account.
