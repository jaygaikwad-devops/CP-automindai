#!/bin/bash
set -e

# AutoMind CP Portal - Deployment Script
# Usage: ./scripts/deploy.sh [all|infra|backend|frontend]

REGION="ap-south-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="automind-api"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "======================================"
echo "AutoMind CP Portal - Deployment"
echo "Account: $ACCOUNT_ID"
echo "Region:  $REGION"
echo "======================================"

deploy_infra() {
  echo "→ Deploying CDK stacks..."
  cd infra
  npx cdk deploy --all --require-approval never
  cd ..
  echo "✓ Infrastructure deployed"
}

deploy_backend() {
  echo "→ Building and pushing backend image..."
  
  # Login to ECR
  aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

  # Create ECR repo if not exists
  aws ecr describe-repositories --repository-names $ECR_REPO --region $REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $ECR_REPO --region $REGION

  # Build and push
  cd backend
  docker build -t $ECR_REPO:$IMAGE_TAG .
  docker tag $ECR_REPO:$IMAGE_TAG $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG
  docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG
  cd ..

  # Force new deployment
  echo "→ Updating ECS service..."
  aws ecs update-service \
    --cluster automind-cluster \
    --service automind-api \
    --force-new-deployment \
    --region $REGION

  echo "✓ Backend deployed"
}

deploy_frontend() {
  echo "→ Building frontend..."
  cd frontend
  npm ci
  npm run build

  # Upload to S3 for CloudFront
  echo "→ Uploading to S3..."
  aws s3 sync out/ s3://automind-cdn-origin-$ACCOUNT_ID-$REGION/ --delete

  # Invalidate CloudFront cache
  DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name AutoMind-Storage \
    --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" \
    --output text --region $REGION 2>/dev/null || echo "")
  
  if [ -n "$DISTRIBUTION_ID" ]; then
    echo "→ Invalidating CloudFront cache..."
    aws cloudfront create-invalidation \
      --distribution-id $DISTRIBUTION_ID \
      --paths "/*"
  fi

  cd ..
  echo "✓ Frontend deployed"
}

# Run migrations
run_migrations() {
  echo "→ Running database migrations..."
  cd backend
  python3 -m alembic upgrade head
  cd ..
  echo "✓ Migrations complete"
}

case "${1:-all}" in
  infra)
    deploy_infra
    ;;
  backend)
    deploy_backend
    ;;
  frontend)
    deploy_frontend
    ;;
  migrate)
    run_migrations
    ;;
  all)
    deploy_infra
    run_migrations
    deploy_backend
    deploy_frontend
    echo ""
    echo "======================================"
    echo "✓ Full deployment complete!"
    echo "======================================"
    ;;
  *)
    echo "Usage: $0 [all|infra|backend|frontend|migrate]"
    exit 1
    ;;
esac
