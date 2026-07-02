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

const vpcStack = new VpcStack(app, 'AutoMind-Vpc', { env });

// Storage stack now includes CloudFront distribution (OAC requires same stack as bucket)
const storageStack = new StorageStack(app, 'AutoMind-Storage', { env });

const databaseStack = new DatabaseStack(app, 'AutoMind-Database', {
  env,
  vpc: vpcStack.vpc,
});

const queueStack = new QueueStack(app, 'AutoMind-Queue', { env });

const computeStack = new ComputeStack(app, 'AutoMind-Compute', {
  env,
  vpc: vpcStack.vpc,
});

const lambdaStack = new LambdaStack(app, 'AutoMind-Lambda', { env });

const authStack = new AuthStack(app, 'AutoMind-Auth', { env });

app.synth();
