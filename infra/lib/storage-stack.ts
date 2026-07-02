import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import { Construct } from 'constructs';

export class StorageStack extends cdk.Stack {
  public readonly assetsBucket: s3.Bucket;
  public readonly tourScriptsBucket: s3.Bucket;
  public readonly cdnOriginBucket: s3.Bucket;
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================================
    // S3 Buckets
    // =========================================================================

    // S3 Bucket for raw project assets (images, videos, PDFs, floor plans)
    this.assetsBucket = new s3.Bucket(this, 'AssetsBucket', {
      bucketName: `automind-assets-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: 'TransitionToIA',
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
        },
      ],
      cors: [
        {
          allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.POST],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 3000,
        },
      ],
    });

    // S3 Bucket for processed tour scripts
    this.tourScriptsBucket = new s3.Bucket(this, 'TourScriptsBucket', {
      bucketName: `automind-tour-scripts-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // S3 Bucket for CDN origin (publicly served content via CloudFront OAC)
    this.cdnOriginBucket = new s3.Bucket(this, 'CdnOriginBucket', {
      bucketName: `automind-cdn-origin-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 86400,
        },
      ],
    });

    // =========================================================================
    // CloudFront Distribution (same stack as bucket to avoid cyclic deps with OAC)
    // =========================================================================

    this.distribution = new cloudfront.Distribution(this, 'CdnDistribution', {
      comment: 'AutoMind AI Platform CDN',
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(this.cdnOriginBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
        compress: true,
      },
      priceClass: cloudfront.PriceClass.PRICE_CLASS_200,
      enabled: true,
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 404,
          responsePagePath: '/404.html',
          ttl: cdk.Duration.minutes(5),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 404,
          responsePagePath: '/404.html',
          ttl: cdk.Duration.minutes(5),
        },
      ],
    });

    // =========================================================================
    // Outputs
    // =========================================================================

    new cdk.CfnOutput(this, 'AssetsBucketName', {
      value: this.assetsBucket.bucketName,
      description: 'Raw assets S3 bucket name',
      exportName: 'AutoMind-AssetsBucketName',
    });

    new cdk.CfnOutput(this, 'AssetsBucketArn', {
      value: this.assetsBucket.bucketArn,
      description: 'Raw assets S3 bucket ARN',
      exportName: 'AutoMind-AssetsBucketArn',
    });

    new cdk.CfnOutput(this, 'TourScriptsBucketName', {
      value: this.tourScriptsBucket.bucketName,
      description: 'Tour scripts S3 bucket name',
      exportName: 'AutoMind-TourScriptsBucketName',
    });

    new cdk.CfnOutput(this, 'CdnOriginBucketName', {
      value: this.cdnOriginBucket.bucketName,
      description: 'CDN origin S3 bucket name',
      exportName: 'AutoMind-CdnOriginBucketName',
    });

    new cdk.CfnOutput(this, 'CdnOriginBucketArn', {
      value: this.cdnOriginBucket.bucketArn,
      description: 'CDN origin S3 bucket ARN',
      exportName: 'AutoMind-CdnOriginBucketArn',
    });

    new cdk.CfnOutput(this, 'DistributionId', {
      value: this.distribution.distributionId,
      description: 'CloudFront Distribution ID',
      exportName: 'AutoMind-DistributionId',
    });

    new cdk.CfnOutput(this, 'DistributionDomainName', {
      value: this.distribution.distributionDomainName,
      description: 'CloudFront Distribution Domain Name',
      exportName: 'AutoMind-DistributionDomainName',
    });
  }
}
