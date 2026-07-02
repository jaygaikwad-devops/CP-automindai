import * as cdk from 'aws-cdk-lib';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { Construct } from 'constructs';

export class QueueStack extends cdk.Stack {
  public readonly processingQueue: sqs.Queue;
  public readonly deadLetterQueue: sqs.Queue;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Dead Letter Queue for failed processing jobs
    this.deadLetterQueue = new sqs.Queue(this, 'DeadLetterQueue', {
      queueName: 'automind-dead-letter-queue',
      retentionPeriod: cdk.Duration.days(14),
      encryption: sqs.QueueEncryption.SQS_MANAGED,
    });

    // Processing Queue for AI pipeline jobs
    this.processingQueue = new sqs.Queue(this, 'ProcessingQueue', {
      queueName: 'automind-processing-queue',
      visibilityTimeout: cdk.Duration.minutes(15),
      retentionPeriod: cdk.Duration.days(4),
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      deadLetterQueue: {
        queue: this.deadLetterQueue,
        maxReceiveCount: 3,
      },
    });

    // Outputs
    new cdk.CfnOutput(this, 'ProcessingQueueUrl', {
      value: this.processingQueue.queueUrl,
      description: 'SQS Processing Queue URL',
      exportName: 'AutoMind-ProcessingQueueUrl',
    });

    new cdk.CfnOutput(this, 'ProcessingQueueArn', {
      value: this.processingQueue.queueArn,
      description: 'SQS Processing Queue ARN',
      exportName: 'AutoMind-ProcessingQueueArn',
    });

    new cdk.CfnOutput(this, 'DeadLetterQueueUrl', {
      value: this.deadLetterQueue.queueUrl,
      description: 'SQS Dead Letter Queue URL',
      exportName: 'AutoMind-DeadLetterQueueUrl',
    });

    new cdk.CfnOutput(this, 'DeadLetterQueueArn', {
      value: this.deadLetterQueue.queueArn,
      description: 'SQS Dead Letter Queue ARN',
      exportName: 'AutoMind-DeadLetterQueueArn',
    });
  }
}
