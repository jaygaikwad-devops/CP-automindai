import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export interface ComputeStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
}

export class ComputeStack extends cdk.Stack {
  public readonly cluster: ecs.Cluster;
  public readonly service: ecs.FargateService;
  public readonly alb: elbv2.ApplicationLoadBalancer;
  public readonly listener: elbv2.ApplicationListener;

  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    const { vpc } = props;

    // =========================================================================
    // ECS Cluster
    // =========================================================================
    this.cluster = new ecs.Cluster(this, 'AutoMindCluster', {
      clusterName: 'automind-cluster',
      vpc,
      containerInsights: true,
    });

    // =========================================================================
    // Task Execution Role (pulls images, writes logs)
    // =========================================================================
    const executionRole = new iam.Role(this, 'TaskExecutionRole', {
      roleName: 'automind-task-execution-role',
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          'service-role/AmazonECSTaskExecutionRolePolicy'
        ),
      ],
    });

    // Allow reading RDS secret
    executionRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        resources: [
          `arn:aws:secretsmanager:${this.region}:${this.account}:secret:automind/*`,
        ],
      })
    );

    // =========================================================================
    // Task Role (what the container can do at runtime)
    // =========================================================================
    const taskRole = new iam.Role(this, 'TaskRole', {
      roleName: 'automind-task-role',
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });

    // Grant access to DynamoDB, S3, SQS, Bedrock, Cognito
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'dynamodb:GetItem',
          'dynamodb:PutItem',
          'dynamodb:UpdateItem',
          'dynamodb:Query',
        ],
        resources: [
          `arn:aws:dynamodb:${this.region}:${this.account}:table/automind_sessions`,
          `arn:aws:dynamodb:${this.region}:${this.account}:table/automind_sessions/index/*`,
        ],
      })
    );

    taskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject', 's3:PutObject', 's3:ListBucket'],
        resources: [
          `arn:aws:s3:::automind-assets-${this.account}-${this.region}`,
          `arn:aws:s3:::automind-assets-${this.account}-${this.region}/*`,
          `arn:aws:s3:::automind-tour-scripts-${this.account}-${this.region}`,
          `arn:aws:s3:::automind-tour-scripts-${this.account}-${this.region}/*`,
        ],
      })
    );

    taskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['sqs:SendMessage'],
        resources: [
          `arn:aws:sqs:${this.region}:${this.account}:automind-processing-queue`,
        ],
      })
    );

    taskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
          'bedrock:Retrieve',
          'bedrock:RetrieveAndGenerate',
        ],
        resources: ['*'],
      })
    );

    taskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'cognito-idp:AdminInitiateAuth',
          'cognito-idp:AdminRespondToAuthChallenge',
          'cognito-idp:AdminGetUser',
          'cognito-idp:AdminCreateUser',
        ],
        resources: [
          `arn:aws:cognito-idp:${this.region}:${this.account}:userpool/*`,
        ],
      })
    );

    taskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        resources: [
          `arn:aws:secretsmanager:${this.region}:${this.account}:secret:automind/*`,
        ],
      })
    );

    // =========================================================================
    // Task Definition
    // =========================================================================
    const taskDefinition = new ecs.FargateTaskDefinition(
      this,
      'ApiTaskDef',
      {
        family: 'automind-api',
        cpu: 512,
        memoryLimitMiB: 1024,
        executionRole,
        taskRole,
      }
    );

    // CloudWatch log group
    const logGroup = new logs.LogGroup(this, 'ApiLogGroup', {
      logGroupName: '/ecs/automind-api',
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Container definition
    const container = taskDefinition.addContainer('api', {
      containerName: 'automind-api',
      // Real application image from ECR
      image: ecs.ContainerImage.fromEcrRepository(
        ecr.Repository.fromRepositoryName(this, 'ApiRepo', 'automind-api'),
        'latest'
      ),
      logging: ecs.LogDrivers.awsLogs({
        logGroup,
        streamPrefix: 'api',
      }),
      environment: {
        AWS_REGION: this.region,
        DYNAMODB_TABLE: 'automind_sessions',
        SQS_PROCESSING_QUEUE_URL: `https://sqs.${this.region}.amazonaws.com/${this.account}/automind-processing-queue`,
        REDIS_HOST: cdk.Fn.importValue('AutoMind-RedisEndpoint'),
        RDS_HOST: cdk.Fn.importValue('AutoMind-RdsEndpoint'),
        RDS_DB_NAME: 'automind',
        RDS_PORT: '5432',
      },
      secrets: {
        RDS_SECRET_ARN: ecs.Secret.fromSecretsManager(
          secretsmanager.Secret.fromSecretNameV2(
            this,
            'RdsSecret',
            'automind/rds/credentials'
          )
        ),
      },
      portMappings: [
        {
          containerPort: 8000,
          protocol: ecs.Protocol.TCP,
        },
      ],
      healthCheck: {
        command: [
          'CMD-SHELL',
          'curl -f http://localhost:8000/health || exit 1',
        ],
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        retries: 3,
        startPeriod: cdk.Duration.seconds(60),
      },
    });

    // =========================================================================
    // ALB (Application Load Balancer)
    // =========================================================================
    this.alb = new elbv2.ApplicationLoadBalancer(this, 'ApiAlb', {
      loadBalancerName: 'automind-api-alb',
      vpc,
      internetFacing: true,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC,
      },
    });

    // HTTP listener (will upgrade to HTTPS when domain + cert are ready)
    this.listener = this.alb.addListener('HttpListener', {
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
    });

    // =========================================================================
    // Fargate Service
    // =========================================================================
    const serviceSg = new ec2.SecurityGroup(this, 'ServiceSg', {
      vpc,
      securityGroupName: 'automind-api-service-sg',
      description: 'Security group for AutoMind API Fargate service',
    });

    // Allow ALB to reach the service
    serviceSg.addIngressRule(
      ec2.Peer.securityGroupId(this.alb.connections.securityGroups[0].securityGroupId),
      ec2.Port.tcp(8000),
      'Allow ALB to reach API service'
    );

    this.service = new ecs.FargateService(this, 'ApiService', {
      serviceName: 'automind-api',
      cluster: this.cluster,
      taskDefinition,
      desiredCount: 1,
      securityGroups: [serviceSg],
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      assignPublicIp: false,
      circuitBreaker: {
        rollback: true,
      },
      enableExecuteCommand: true, // For debugging via ECS Exec
    });

    // Register service with ALB target group
    const targetGroup = this.listener.addTargets('ApiTargetGroup', {
      targetGroupName: 'automind-api-tg',
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [this.service],
      healthCheck: {
        path: '/health',
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
        healthyHttpCodes: '200',
      },
      deregistrationDelay: cdk.Duration.seconds(30),
    });

    // =========================================================================
    // Auto-Scaling (min 1, max 4)
    // =========================================================================
    const scaling = this.service.autoScaleTaskCount({
      minCapacity: 1,
      maxCapacity: 4,
    });

    scaling.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.seconds(300),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    scaling.scaleOnMemoryUtilization('MemoryScaling', {
      targetUtilizationPercent: 80,
      scaleInCooldown: cdk.Duration.seconds(300),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // =========================================================================
    // Outputs
    // =========================================================================
    new cdk.CfnOutput(this, 'AlbDnsName', {
      value: this.alb.loadBalancerDnsName,
      description: 'ALB DNS name for the API',
      exportName: 'AutoMind-AlbDnsName',
    });

    new cdk.CfnOutput(this, 'AlbArn', {
      value: this.alb.loadBalancerArn,
      description: 'ALB ARN',
      exportName: 'AutoMind-AlbArn',
    });

    new cdk.CfnOutput(this, 'ClusterName', {
      value: this.cluster.clusterName,
      description: 'ECS Cluster name',
      exportName: 'AutoMind-ClusterName',
    });

    new cdk.CfnOutput(this, 'ServiceName', {
      value: this.service.serviceName,
      description: 'ECS Service name',
      exportName: 'AutoMind-ServiceName',
    });
  }
}
