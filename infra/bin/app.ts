#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { VpcStack } from '../lib/vpc-stack';
import { StorageStack } from '../lib/storage-stack';
import { DatabaseStack } from '../lib/database-stack';
import { QueueStack } from '../lib/queue-stack';
import { ComputeStack } from '../lib/compute-stack';
import { LambdaStack } from '../lib/lambda-stack';
import { AuthStack } from '../lib/auth-stack';

const app = new cdk.App();

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: 'ap-south-1',
};

// =========================================================================
// Stack Composition with Cross-Stack References
// =========================================================================

// Layer 1: Network foundation
const vpcStack = new VpcStack(app, 'AutoMind-Vpc', { env });

// Layer 2: Storage (S3 + CloudFront)
const storageStack = new StorageStack(app, 'AutoMind-Storage', { env });

// Layer 3: Data (RDS + DynamoDB + Redis) — depends on VPC
const databaseStack = new DatabaseStack(app, 'AutoMind-Database', {
  env,
  vpc: vpcStack.vpc,
});
databaseStack.addDependency(vpcStack);

// Layer 4: Messaging (SQS queues)
const queueStack = new QueueStack(app, 'AutoMind-Queue', { env });

// Layer 5: Compute (ECS Fargate + ALB) — depends on VPC
const computeStack = new ComputeStack(app, 'AutoMind-Compute', {
  env,
  vpc: vpcStack.vpc,
});
computeStack.addDependency(vpcStack);
computeStack.addDependency(databaseStack);

// Layer 6: Lambda workers — triggered by SQS
const lambdaStack = new LambdaStack(app, 'AutoMind-Lambda', { env });
lambdaStack.addDependency(queueStack);
lambdaStack.addDependency(storageStack);

// Layer 7: Auth (Cognito + API Gateway WebSocket)
const authStack = new AuthStack(app, 'AutoMind-Auth', { env });

app.synth();
