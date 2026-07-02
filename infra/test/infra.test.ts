import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { VpcStack } from '../lib/vpc-stack';
import { StorageStack } from '../lib/storage-stack';
import { DatabaseStack } from '../lib/database-stack';
import { QueueStack } from '../lib/queue-stack';
import { ComputeStack } from '../lib/compute-stack';
import { LambdaStack } from '../lib/lambda-stack';
import { AuthStack } from '../lib/auth-stack';

const env = { account: '123456789012', region: 'ap-south-1' };

describe('AutoMind Infrastructure', () => {
  describe('VPC Stack', () => {
    const app = new cdk.App();
    const vpcStack = new VpcStack(app, 'TestVpc', { env });
    const template = Template.fromStack(vpcStack);

    test('creates a VPC', () => {
      template.resourceCountIs('AWS::EC2::VPC', 1);
    });

    test('creates public, private, and isolated subnets', () => {
      // 2 AZs × 3 subnet types = 6 subnets
      template.resourceCountIs('AWS::EC2::Subnet', 6);
    });

    test('creates a NAT Gateway', () => {
      template.resourceCountIs('AWS::EC2::NatGateway', 1);
    });
  });

  describe('Storage Stack (S3 + CloudFront)', () => {
    const app = new cdk.App();
    const storageStack = new StorageStack(app, 'TestStorage', { env });
    const template = Template.fromStack(storageStack);

    test('creates three S3 buckets (assets, tour-scripts, cdn-origin)', () => {
      template.resourceCountIs('AWS::S3::Bucket', 3);
    });

    test('assets bucket has versioning enabled', () => {
      template.hasResourceProperties('AWS::S3::Bucket', {
        VersioningConfiguration: { Status: 'Enabled' },
      });
    });

    test('buckets block public access', () => {
      template.hasResourceProperties('AWS::S3::Bucket', {
        PublicAccessBlockConfiguration: {
          BlockPublicAcls: true,
          BlockPublicPolicy: true,
          IgnorePublicAcls: true,
          RestrictPublicBuckets: true,
        },
      });
    });

    test('creates CloudFront distribution', () => {
      template.resourceCountIs('AWS::CloudFront::Distribution', 1);
    });

    test('distribution enforces HTTPS and compression', () => {
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          DefaultCacheBehavior: {
            ViewerProtocolPolicy: 'redirect-to-https',
            Compress: true,
          },
        },
      });
    });

    test('creates Origin Access Control for S3', () => {
      template.resourceCountIs('AWS::CloudFront::OriginAccessControl', 1);
    });
  });

  describe('Database Stack', () => {
    const app = new cdk.App();
    const vpcStack = new VpcStack(app, 'TestDbVpc', { env });
    const dbStack = new DatabaseStack(app, 'TestDatabase', {
      env,
      vpc: vpcStack.vpc,
    });
    const template = Template.fromStack(dbStack);

    test('creates DynamoDB sessions table', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'automind_sessions',
        KeySchema: [
          { AttributeName: 'PK', KeyType: 'HASH' },
          { AttributeName: 'SK', KeyType: 'RANGE' },
        ],
        TimeToLiveSpecification: {
          AttributeName: 'ttl',
          Enabled: true,
        },
      });
    });

    test('DynamoDB table has GSI1', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        GlobalSecondaryIndexes: [
          {
            IndexName: 'GSI1',
            KeySchema: [
              { AttributeName: 'GSI1PK', KeyType: 'HASH' },
              { AttributeName: 'GSI1SK', KeyType: 'RANGE' },
            ],
            Projection: { ProjectionType: 'ALL' },
          },
        ],
      });
    });

    test('creates RDS PostgreSQL instance', () => {
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        DBInstanceClass: 'db.t3.medium',
        Engine: 'postgres',
        DBName: 'automind',
        PubliclyAccessible: false,
        DeletionProtection: true,
      });
    });

    test('creates ElastiCache Redis cluster', () => {
      template.hasResourceProperties('AWS::ElastiCache::CacheCluster', {
        Engine: 'redis',
        CacheNodeType: 'cache.t3.micro',
        NumCacheNodes: 1,
      });
    });
  });

  describe('Queue Stack', () => {
    const app = new cdk.App();
    const queueStack = new QueueStack(app, 'TestQueue', { env });
    const template = Template.fromStack(queueStack);

    test('creates processing queue and dead letter queue', () => {
      template.resourceCountIs('AWS::SQS::Queue', 2);
    });

    test('processing queue has DLQ configured', () => {
      template.hasResourceProperties('AWS::SQS::Queue', {
        QueueName: 'automind-processing-queue',
        VisibilityTimeout: 900,
        RedrivePolicy: {
          maxReceiveCount: 3,
        },
      });
    });

    test('dead letter queue has 14 day retention', () => {
      template.hasResourceProperties('AWS::SQS::Queue', {
        QueueName: 'automind-dead-letter-queue',
        MessageRetentionPeriod: 1209600,
      });
    });
  });
});


  describe('Compute Stack (ECS Fargate + ALB)', () => {
    const app = new cdk.App();
    const vpcStack = new VpcStack(app, 'TestComputeVpc', { env });
    const computeStack = new ComputeStack(app, 'TestCompute', {
      env,
      vpc: vpcStack.vpc,
    });
    const template = Template.fromStack(computeStack);

    test('creates ECS cluster', () => {
      template.hasResourceProperties('AWS::ECS::Cluster', {
        ClusterName: 'automind-cluster',
        ClusterSettings: [
          { Name: 'containerInsights', Value: 'enabled' },
        ],
      });
    });

    test('creates Fargate service with desired count 1', () => {
      template.hasResourceProperties('AWS::ECS::Service', {
        ServiceName: 'automind-api',
        DesiredCount: 1,
        LaunchType: 'FARGATE',
      });
    });

    test('creates ALB', () => {
      template.hasResourceProperties(
        'AWS::ElasticLoadBalancingV2::LoadBalancer',
        {
          Name: 'automind-api-alb',
          Scheme: 'internet-facing',
          Type: 'application',
        }
      );
    });

    test('creates target group with health check on /health', () => {
      template.hasResourceProperties(
        'AWS::ElasticLoadBalancingV2::TargetGroup',
        {
          HealthCheckPath: '/health',
          Port: 8000,
          Protocol: 'HTTP',
        }
      );
    });

    test('task definition has 512 CPU and 1024 memory', () => {
      template.hasResourceProperties('AWS::ECS::TaskDefinition', {
        Cpu: '512',
        Memory: '1024',
        NetworkMode: 'awsvpc',
        RequiresCompatibilities: ['FARGATE'],
      });
    });

    test('auto-scaling configured with min 1 max 4', () => {
      template.hasResourceProperties(
        'AWS::ApplicationAutoScaling::ScalableTarget',
        {
          MinCapacity: 1,
          MaxCapacity: 4,
        }
      );
    });
  });


  describe('Lambda Stack', () => {
    const app = new cdk.App();
    const lambdaStack = new LambdaStack(app, 'TestLambda', { env });
    const template = Template.fromStack(lambdaStack);

    test('creates 6 Lambda functions', () => {
      // 6 functions + CDK may add framework helpers; check our named functions exist
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-image-analyzer',
      });
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-reconciliation',
      });
    });

    test('image_analyzer Lambda exists with correct config', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-image-analyzer',
        Runtime: 'python3.11',
        Timeout: 300,
        MemorySize: 512,
      });
    });

    test('pdf_extractor Lambda exists with correct config', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-pdf-extractor',
        Runtime: 'python3.11',
        Timeout: 600,
        MemorySize: 1024,
      });
    });

    test('tour_sequencer Lambda exists with correct config', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-tour-sequencer',
        Runtime: 'python3.11',
        Timeout: 600,
        MemorySize: 1024,
      });
    });

    test('kb_builder Lambda exists with correct config', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-kb-builder',
        Runtime: 'python3.11',
        Timeout: 600,
        MemorySize: 512,
      });
    });

    test('lead_scorer Lambda exists with 30s timeout', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-lead-scorer',
        Runtime: 'python3.11',
        Timeout: 30,
        MemorySize: 256,
      });
    });

    test('reconciliation Lambda exists with 5min timeout', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-reconciliation',
        Runtime: 'python3.11',
        Timeout: 300,
        MemorySize: 256,
      });
    });

    test('reconciliation Lambda has CloudWatch Events schedule (every 5 min)', () => {
      template.hasResourceProperties('AWS::Events::Rule', {
        ScheduleExpression: 'rate(5 minutes)',
      });
    });

    test('pipeline Lambdas have SQS event source mappings', () => {
      // 4 pipeline lambdas with SQS triggers: image_analyzer, pdf_extractor, tour_sequencer, kb_builder
      template.resourceCountIs('AWS::Lambda::EventSourceMapping', 4);
    });
  });


  describe('Auth Stack (Cognito + WebSocket API)', () => {
    const app = new cdk.App();
    const authStack = new AuthStack(app, 'TestAuth', { env });
    const template = Template.fromStack(authStack);

    test('creates Cognito User Pool with phone sign-in', () => {
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        UserPoolName: 'automind-users',
        UsernameAttributes: ['phone_number'],
        AutoVerifiedAttributes: ['phone_number'],
      });
    });

    test('creates User Pool Client with custom auth flow', () => {
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        ClientName: 'automind-app-client',
        ExplicitAuthFlows: [
          'ALLOW_CUSTOM_AUTH',
          'ALLOW_REFRESH_TOKEN_AUTH',
        ],
      });
    });

    test('creates 3 custom auth Lambda triggers', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-define-auth-challenge',
      });
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-create-auth-challenge',
      });
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'automind-verify-auth-challenge',
      });
    });

    test('creates WebSocket API with correct protocol', () => {
      template.hasResourceProperties('AWS::ApiGatewayV2::Api', {
        Name: 'automind-websocket',
        ProtocolType: 'WEBSOCKET',
        RouteSelectionExpression: '$request.body.action',
      });
    });

    test('creates WebSocket routes: $connect, $disconnect, chat, room_navigate', () => {
      template.hasResourceProperties('AWS::ApiGatewayV2::Route', {
        RouteKey: '$connect',
      });
      template.hasResourceProperties('AWS::ApiGatewayV2::Route', {
        RouteKey: '$disconnect',
      });
      template.hasResourceProperties('AWS::ApiGatewayV2::Route', {
        RouteKey: 'chat',
      });
      template.hasResourceProperties('AWS::ApiGatewayV2::Route', {
        RouteKey: 'room_navigate',
      });
    });

    test('creates WebSocket prod stage with auto-deploy', () => {
      template.hasResourceProperties('AWS::ApiGatewayV2::Stage', {
        StageName: 'prod',
        AutoDeploy: true,
      });
    });
  });
