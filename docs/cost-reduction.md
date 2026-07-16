# AWS Cost Reduction Plan

**Current Monthly Cost:** ~$192  
**Target Monthly Cost:** ~$60-80  
**Savings:** ~$110-130/month

---

## Cost Breakdown (July 2026)

| Service | Cost | Root Cause | Action |
|---------|------|-----------|--------|
| EC2 Compute | $106.67 | t2.medium instance + NAT Gateway | Stop EC2, remove NAT GW |
| RDS | $40.87 | db.t3.medium (oversized) | Downgrade to db.t3.micro |
| EC2 Other | $27.01 | NAT GW data processing + EBS | Remove NAT GW |
| VPC | $9.19 | NAT Gateway hourly | Remove NAT GW |
| ECS | $9.07 | Fargate 512 CPU / 1024 MB | Reduce to 256 CPU / 512 MB |
| **Total** | **~$192** | | |

---

## Action Items

### 1. Stop/Terminate the EC2 t2.medium (-$35/month)

This instance (`i-086ff05457ef819c2`) appears to be the old Marketing OS v3 app or a bastion host — not needed anymore since ECS runs the API.

```bash
# Stop (can restart later if needed)
aws ec2 stop-instances --instance-ids i-086ff05457ef819c2 --region ap-south-1

# Or terminate permanently
aws ec2 terminate-instances --instance-ids i-086ff05457ef819c2 --region ap-south-1
```

### 2. Remove NAT Gateway (-$45/month)

The NAT Gateway costs $0.045/hour + $0.045/GB data processed (~$32 fixed + $13 data). 

**Alternative:** ECS tasks can use public subnets with `assignPublicIp: true` for internet access (free).

```bash
# Delete NAT Gateway
aws ec2 delete-nat-gateway --nat-gateway-id nat-0378fa69e6e762046 --region ap-south-1

# Update ECS service to use public subnets with public IP
# (Requires updating the CDK compute stack or task definition network config)
```

**After removing NAT GW**, update ECS to assign public IP:
- Move Fargate tasks to public subnets
- Set `assignPublicIp: ENABLED`
- This allows internet access without NAT GW

### 3. Downgrade RDS to db.t3.micro (-$27/month)

db.t3.medium = $0.056/hr (~$40/mo)  
db.t3.micro = $0.019/hr (~$14/mo)

```bash
aws rds modify-db-instance \
  --db-instance-identifier automind-postgres \
  --db-instance-class db.t3.micro \
  --apply-immediately \
  --region ap-south-1
```

⚠️ This causes a brief (~5 min) downtime during the class change.

### 4. Reduce Fargate Task Size (-$4/month)

Current: 512 CPU / 1024 MB  
Recommended: 256 CPU / 512 MB (sufficient for MVP traffic)

Update the task definition:
```json
{
  "cpu": "256",
  "memory": "512"
}
```

### 5. (Optional) Schedule RDS stop during off-hours (-$10/month)

If you don't need the API 24/7 during development:
```bash
# Stop RDS (saves costs when not in use)
aws rds stop-db-instance --db-instance-identifier automind-postgres --region ap-south-1

# Start when needed
aws rds start-db-instance --db-instance-identifier automind-postgres --region ap-south-1
```

---

## Projected Cost After Optimization

| Service | Before | After | Savings |
|---------|--------|-------|---------|
| EC2 (t2.medium) | $35 | $0 | $35 |
| NAT Gateway | $45 | $0 | $45 |
| RDS | $40 | $14 | $26 |
| ECS Fargate | $9 | $5 | $4 |
| VPC (NAT removed) | $9 | $0 | $9 |
| Other (EBS, etc.) | $15 | $10 | $5 |
| CloudFront + S3 | $3 | $3 | $0 |
| DynamoDB | $1 | $1 | $0 |
| Redis | $15 | $15 | $0 |
| Lambda | $0 | $0 | $0 |
| **Total** | **$192** | **$48-60** | **$132-144** |

---

## Execute Cost Reduction

Run these commands to immediately reduce costs:
