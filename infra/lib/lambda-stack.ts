import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export class LambdaStack extends cdk.Stack {
  public readonly imageAnalyzer: lambda.Function;
  public readonly pdfExtractor: lambda.Function;
  public readonly tourSequencer: lambda.Function;
  public readonly kbBuilder: lambda.Function;
  public readonly leadScorer: lambda.Function;
  public readonly reconciliation: lambda.Function;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================================
    // Shared IAM policies
    // =========================================================================
    const dynamoDbPolicy = new iam.PolicyStatement({
      actions: [
        'dynamodb:GetItem',
        'dynamodb:PutItem',
        'dynamodb:UpdateItem',
        'dynamodb:Query',
        'dynamodb:Scan',
      ],
      resources: [
        `arn:aws:dynamodb:${this.region}:${this.account}:table/automind_sessions`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/automind_sessions/index/*`,
      ],
    });

    const s3ReadWritePolicy = new iam.PolicyStatement({
      actions: ['s3:GetObject', 's3:PutObject', 's3:ListBucket'],
      resources: [
        `arn:aws:s3:::automind-assets-${this.account}-${this.region}`,
        `arn:aws:s3:::automind-assets-${this.account}-${this.region}/*`,
        `arn:aws:s3:::automind-tour-scripts-${this.account}-${this.region}`,
        `arn:aws:s3:::automind-tour-scripts-${this.account}-${this.region}/*`,
      ],
    });

    const rdsPolicy = new iam.PolicyStatement({
      actions: ['secretsmanager:GetSecretValue'],
      resources: [
        `arn:aws:secretsmanager:${this.region}:${this.account}:secret:automind/*`,
      ],
    });

    const sqsSendPolicy = new iam.PolicyStatement({
      actions: ['sqs:SendMessage'],
      resources: [
        `arn:aws:sqs:${this.region}:${this.account}:automind-processing-queue`,
      ],
    });

    // =========================================================================
    // Import SQS queue
    // =========================================================================
    const processingQueue = sqs.Queue.fromQueueArn(
      this,
      'ProcessingQueue',
      `arn:aws:sqs:${this.region}:${this.account}:automind-processing-queue`
    );

    // =========================================================================
    // 1. Image Analyzer Lambda (Rekognition)
    // =========================================================================
    this.imageAnalyzer = new lambda.Function(this, 'ImageAnalyzer', {
      functionName: 'automind-image-analyzer',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromInline(
        'def lambda_handler(event, context): return {"statusCode": 200, "body": "placeholder"}'
      ),
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      retryAttempts: 2,
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        ASSETS_BUCKET: `automind-assets-${this.account}-${this.region}`,
        TOUR_SCRIPTS_BUCKET: `automind-tour-scripts-${this.account}-${this.region}`,
        AWS_REGION_NAME: this.region,
      },
    });

    this.imageAnalyzer.addToRolePolicy(s3ReadWritePolicy);
    this.imageAnalyzer.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['rekognition:DetectLabels', 'rekognition:DetectText'],
        resources: ['*'],
      })
    );

    // SQS trigger for image_analyzer
    this.imageAnalyzer.addEventSource(
      new lambdaEventSources.SqsEventSource(processingQueue, {
        batchSize: 1,
        maxConcurrency: 5,
        filters: [
          lambda.FilterCriteria.filter({
            body: { job_type: lambda.FilterRule.isEqual('image_analysis') },
          }),
        ],
      })
    );

    // =========================================================================
    // 2. PDF Extractor Lambda (Textract + Bedrock)
    // =========================================================================
    this.pdfExtractor = new lambda.Function(this, 'PdfExtractor', {
      functionName: 'automind-pdf-extractor',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromInline(
        'def lambda_handler(event, context): return {"statusCode": 200, "body": "placeholder"}'
      ),
      timeout: cdk.Duration.minutes(10),
      memorySize: 1024,
      retryAttempts: 2,
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        ASSETS_BUCKET: `automind-assets-${this.account}-${this.region}`,
        TOUR_SCRIPTS_BUCKET: `automind-tour-scripts-${this.account}-${this.region}`,
        AWS_REGION_NAME: this.region,
      },
    });

    this.pdfExtractor.addToRolePolicy(s3ReadWritePolicy);
    this.pdfExtractor.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'textract:AnalyzeDocument',
          'textract:DetectDocumentText',
          'textract:StartDocumentAnalysis',
          'textract:GetDocumentAnalysis',
        ],
        resources: ['*'],
      })
    );
    this.pdfExtractor.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: ['*'],
      })
    );

    // SQS trigger for pdf_extractor
    this.pdfExtractor.addEventSource(
      new lambdaEventSources.SqsEventSource(processingQueue, {
        batchSize: 1,
        maxConcurrency: 3,
        filters: [
          lambda.FilterCriteria.filter({
            body: { job_type: lambda.FilterRule.isEqual('pdf_extraction') },
          }),
        ],
      })
    );

    // =========================================================================
    // 3. Tour Sequencer Lambda (Bedrock — builds tour-script.json)
    // =========================================================================
    this.tourSequencer = new lambda.Function(this, 'TourSequencer', {
      functionName: 'automind-tour-sequencer',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromInline(
        'def lambda_handler(event, context): return {"statusCode": 200, "body": "placeholder"}'
      ),
      timeout: cdk.Duration.minutes(10),
      memorySize: 1024,
      retryAttempts: 2,
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        ASSETS_BUCKET: `automind-assets-${this.account}-${this.region}`,
        TOUR_SCRIPTS_BUCKET: `automind-tour-scripts-${this.account}-${this.region}`,
        AWS_REGION_NAME: this.region,
      },
    });

    this.tourSequencer.addToRolePolicy(s3ReadWritePolicy);
    this.tourSequencer.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: ['*'],
      })
    );

    // SQS trigger for tour_sequencer
    this.tourSequencer.addEventSource(
      new lambdaEventSources.SqsEventSource(processingQueue, {
        batchSize: 1,
        maxConcurrency: 2,
        filters: [
          lambda.FilterCriteria.filter({
            body: { job_type: lambda.FilterRule.isEqual('tour_sequencing') },
          }),
        ],
      })
    );

    // =========================================================================
    // 4. KB Builder Lambda (Bedrock Knowledge Bases ingestion)
    // =========================================================================
    this.kbBuilder = new lambda.Function(this, 'KbBuilder', {
      functionName: 'automind-kb-builder',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromInline(
        'def lambda_handler(event, context): return {"statusCode": 200, "body": "placeholder"}'
      ),
      timeout: cdk.Duration.minutes(10),
      memorySize: 512,
      retryAttempts: 2,
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        TOUR_SCRIPTS_BUCKET: `automind-tour-scripts-${this.account}-${this.region}`,
        AWS_REGION_NAME: this.region,
      },
    });

    this.kbBuilder.addToRolePolicy(s3ReadWritePolicy);
    this.kbBuilder.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock:CreateKnowledgeBase',
          'bedrock:UpdateKnowledgeBase',
          'bedrock:StartIngestionJob',
          'bedrock:GetIngestionJob',
          'bedrock:CreateDataSource',
          'bedrock:UpdateDataSource',
        ],
        resources: ['*'],
      })
    );

    // SQS trigger for kb_builder
    this.kbBuilder.addEventSource(
      new lambdaEventSources.SqsEventSource(processingQueue, {
        batchSize: 1,
        maxConcurrency: 2,
        filters: [
          lambda.FilterCriteria.filter({
            body: { job_type: lambda.FilterRule.isEqual('kb_building') },
          }),
        ],
      })
    );

    // =========================================================================
    // 5. Lead Scorer Lambda (non-chat events)
    // =========================================================================
    this.leadScorer = new lambda.Function(this, 'LeadScorer', {
      functionName: 'automind-lead-scorer',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromInline(
        'def lambda_handler(event, context): return {"statusCode": 200, "body": "placeholder"}'
      ),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      retryAttempts: 2,
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        DYNAMODB_TABLE: 'automind_sessions',
        ALERT_THRESHOLD: '7',
        AWS_REGION_NAME: this.region,
      },
    });

    this.leadScorer.addToRolePolicy(dynamoDbPolicy);
    this.leadScorer.addToRolePolicy(rdsPolicy);
    // Gupshup WhatsApp + SNS for alerts
    this.leadScorer.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['sns:Publish'],
        resources: [`arn:aws:sns:${this.region}:${this.account}:automind-*`],
      })
    );

    // =========================================================================
    // 6. Background Reconciliation Lambda (DynamoDB → RDS sync)
    // =========================================================================
    this.reconciliation = new lambda.Function(this, 'Reconciliation', {
      functionName: 'automind-reconciliation',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromInline(
        'def lambda_handler(event, context): return {"statusCode": 200, "body": "placeholder"}'
      ),
      timeout: cdk.Duration.minutes(5),
      memorySize: 256,
      retryAttempts: 0,
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        DYNAMODB_TABLE: 'automind_sessions',
        AWS_REGION_NAME: this.region,
      },
    });

    this.reconciliation.addToRolePolicy(dynamoDbPolicy);
    this.reconciliation.addToRolePolicy(rdsPolicy);

    // CloudWatch Events: run every 5 minutes
    const reconciliationRule = new events.Rule(this, 'ReconciliationSchedule', {
      ruleName: 'automind-reconciliation-schedule',
      schedule: events.Schedule.rate(cdk.Duration.minutes(5)),
      description: 'Triggers DynamoDB-to-RDS reconciliation every 5 minutes',
    });

    reconciliationRule.addTarget(
      new targets.LambdaFunction(this.reconciliation, {
        retryAttempts: 0,
      })
    );

    // =========================================================================
    // Outputs
    // =========================================================================
    new cdk.CfnOutput(this, 'ImageAnalyzerArn', {
      value: this.imageAnalyzer.functionArn,
      description: 'Image Analyzer Lambda ARN',
      exportName: 'AutoMind-ImageAnalyzerArn',
    });

    new cdk.CfnOutput(this, 'PdfExtractorArn', {
      value: this.pdfExtractor.functionArn,
      description: 'PDF Extractor Lambda ARN',
      exportName: 'AutoMind-PdfExtractorArn',
    });

    new cdk.CfnOutput(this, 'TourSequencerArn', {
      value: this.tourSequencer.functionArn,
      description: 'Tour Sequencer Lambda ARN',
      exportName: 'AutoMind-TourSequencerArn',
    });

    new cdk.CfnOutput(this, 'KbBuilderArn', {
      value: this.kbBuilder.functionArn,
      description: 'KB Builder Lambda ARN',
      exportName: 'AutoMind-KbBuilderArn',
    });

    new cdk.CfnOutput(this, 'LeadScorerArn', {
      value: this.leadScorer.functionArn,
      description: 'Lead Scorer Lambda ARN',
      exportName: 'AutoMind-LeadScorerArn',
    });

    new cdk.CfnOutput(this, 'ReconciliationArn', {
      value: this.reconciliation.functionArn,
      description: 'Reconciliation Lambda ARN',
      exportName: 'AutoMind-ReconciliationArn',
    });
  }
}
