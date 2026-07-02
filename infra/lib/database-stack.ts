import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as elasticache from 'aws-cdk-lib/aws-elasticache';
import { Construct } from 'constructs';

export interface DatabaseStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
}

export class DatabaseStack extends cdk.Stack {
  public readonly sessionsTable: dynamodb.Table;
  public readonly rdsInstance: rds.DatabaseInstance;
  public readonly redisSecurityGroup: ec2.SecurityGroup;
  public readonly rdsSecurityGroup: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {
    super(scope, id, props);

    const { vpc } = props;

    // =========================================================================
    // DynamoDB: automind_sessions table
    // =========================================================================
    this.sessionsTable = new dynamodb.Table(this, 'SessionsTable', {
      tableName: 'automind_sessions',
      partitionKey: {
        name: 'PK',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'SK',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecovery: true,
    });

    // GSI1: Query CP hot leads sorted by score
    // PK = CP#{cp_id}, SK = SCORE#{zero-padded-inverted-score}#{created_at}
    this.sessionsTable.addGlobalSecondaryIndex({
      indexName: 'GSI1',
      partitionKey: {
        name: 'GSI1PK',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'GSI1SK',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // =========================================================================
    // RDS PostgreSQL instance
    // =========================================================================
    this.rdsSecurityGroup = new ec2.SecurityGroup(this, 'RdsSecurityGroup', {
      vpc,
      securityGroupName: 'automind-rds-sg',
      description: 'Security group for AutoMind RDS PostgreSQL',
      allowAllOutbound: false,
    });

    this.rdsInstance = new rds.DatabaseInstance(this, 'PostgresInstance', {
      instanceIdentifier: 'automind-postgres',
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.of('15.17', '15'),
      }),
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T3,
        ec2.InstanceSize.MEDIUM
      ),
      vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
      },
      securityGroups: [this.rdsSecurityGroup],
      databaseName: 'automind',
      credentials: rds.Credentials.fromGeneratedSecret('automind_admin', {
        secretName: 'automind/rds/credentials',
      }),
      allocatedStorage: 50,
      maxAllocatedStorage: 200,
      storageEncrypted: true,
      multiAz: false,
      autoMinorVersionUpgrade: true,
      backupRetention: cdk.Duration.days(7),
      deletionProtection: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      publiclyAccessible: false,
    });

    // =========================================================================
    // ElastiCache Redis cluster
    // =========================================================================
    this.redisSecurityGroup = new ec2.SecurityGroup(this, 'RedisSecurityGroup', {
      vpc,
      securityGroupName: 'automind-redis-sg',
      description: 'Security group for AutoMind ElastiCache Redis',
      allowAllOutbound: false,
    });

    const redisSubnetGroup = new elasticache.CfnSubnetGroup(
      this,
      'RedisSubnetGroup',
      {
        cacheSubnetGroupName: 'automind-redis-subnet-group',
        description: 'Subnet group for AutoMind Redis cluster',
        subnetIds: vpc.selectSubnets({
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        }).subnetIds,
      }
    );

    const redisCluster = new elasticache.CfnCacheCluster(this, 'RedisCluster', {
      clusterName: 'automind-redis',
      engine: 'redis',
      cacheNodeType: 'cache.t3.micro',
      numCacheNodes: 1,
      port: 6379,
      vpcSecurityGroupIds: [this.redisSecurityGroup.securityGroupId],
      cacheSubnetGroupName: redisSubnetGroup.cacheSubnetGroupName!,
      engineVersion: '7.1',
      autoMinorVersionUpgrade: true,
    });

    redisCluster.addDependency(redisSubnetGroup);

    // =========================================================================
    // Outputs
    // =========================================================================
    new cdk.CfnOutput(this, 'SessionsTableName', {
      value: this.sessionsTable.tableName,
      description: 'DynamoDB sessions table name',
      exportName: 'AutoMind-SessionsTableName',
    });

    new cdk.CfnOutput(this, 'SessionsTableArn', {
      value: this.sessionsTable.tableArn,
      description: 'DynamoDB sessions table ARN',
      exportName: 'AutoMind-SessionsTableArn',
    });

    new cdk.CfnOutput(this, 'RdsEndpoint', {
      value: this.rdsInstance.instanceEndpoint.hostname,
      description: 'RDS PostgreSQL endpoint',
      exportName: 'AutoMind-RdsEndpoint',
    });

    new cdk.CfnOutput(this, 'RdsSecretArn', {
      value: this.rdsInstance.secret?.secretArn || '',
      description: 'RDS credentials secret ARN',
      exportName: 'AutoMind-RdsSecretArn',
    });

    new cdk.CfnOutput(this, 'RedisEndpoint', {
      value: redisCluster.attrRedisEndpointAddress,
      description: 'ElastiCache Redis endpoint',
      exportName: 'AutoMind-RedisEndpoint',
    });
  }
}
