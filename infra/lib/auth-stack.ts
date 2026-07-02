import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as apigatewayv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class AuthStack extends cdk.Stack {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly websocketApi: apigatewayv2.CfnApi;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================================
    // Cognito Custom Auth Lambda Triggers
    // =========================================================================

    // Define Auth Challenge — decides flow steps
    const defineAuthChallenge = new lambda.Function(this, 'DefineAuthChallenge', {
      functionName: 'automind-define-auth-challenge',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromInline(`
def lambda_handler(event, context):
    session = event['request']['session']
    if len(session) == 0:
        event['response']['challengeName'] = 'CUSTOM_CHALLENGE'
        event['response']['issueTokens'] = False
        event['response']['failAuthentication'] = False
    elif len(session) == 1 and session[0]['challengeResult'] == True:
        event['response']['issueTokens'] = True
        event['response']['failAuthentication'] = False
    else:
        event['response']['issueTokens'] = False
        event['response']['failAuthentication'] = True
    return event
`),
      timeout: cdk.Duration.seconds(10),
      memorySize: 128,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Create Auth Challenge — sends OTP via SMS
    const createAuthChallenge = new lambda.Function(this, 'CreateAuthChallenge', {
      functionName: 'automind-create-auth-challenge',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromInline(`
import random
import boto3

def lambda_handler(event, context):
    otp = str(random.randint(100000, 999999))
    phone = event['request']['userAttributes']['phone_number']
    
    # Store OTP as private challenge parameter
    event['response']['privateChallengeParameters'] = {'otp': otp}
    event['response']['publicChallengeParameters'] = {'phone': phone[-4:]}
    event['response']['challengeMetadata'] = f'OTP-{otp}'
    
    # Send OTP via SNS
    sns = boto3.client('sns')
    sns.publish(
        PhoneNumber=phone,
        Message=f'Your AutoMind verification code is: {otp}. Valid for 5 minutes.',
        MessageAttributes={
            'AWS.SNS.SMS.SMSType': {
                'DataType': 'String',
                'StringValue': 'Transactional'
            }
        }
    )
    return event
`),
      timeout: cdk.Duration.seconds(15),
      memorySize: 128,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant SNS publish permission for OTP delivery
    createAuthChallenge.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['sns:Publish'],
        resources: ['*'], // SNS Publish to phone numbers requires * resource
      })
    );

    // Verify Auth Challenge — checks OTP
    const verifyAuthChallenge = new lambda.Function(this, 'VerifyAuthChallenge', {
      functionName: 'automind-verify-auth-challenge',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromInline(`
def lambda_handler(event, context):
    expected_otp = event['request']['privateChallengeParameters']['otp']
    user_otp = event['request']['challengeAnswer']
    event['response']['answerCorrect'] = (expected_otp == user_otp)
    return event
`),
      timeout: cdk.Duration.seconds(10),
      memorySize: 128,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // =========================================================================
    // Cognito User Pool
    // =========================================================================
    this.userPool = new cognito.UserPool(this, 'AutoMindUserPool', {
      userPoolName: 'automind-users',
      selfSignUpEnabled: true,
      signInAliases: {
        phone: true,
      },
      autoVerify: {
        phone: true,
      },
      standardAttributes: {
        phoneNumber: {
          required: true,
          mutable: false,
        },
        fullname: {
          required: false,
          mutable: true,
        },
      },
      customAttributes: {
        rera_id: new cognito.StringAttribute({ mutable: true }),
        role: new cognito.StringAttribute({ mutable: true }), // 'cp' | 'admin'
        city: new cognito.StringAttribute({ mutable: true }),
      },
      passwordPolicy: {
        minLength: 8, // Required by Cognito even with custom auth
        requireLowercase: false,
        requireUppercase: false,
        requireDigits: false,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.PHONE_ONLY_WITHOUT_MFA,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lambdaTriggers: {
        defineAuthChallenge,
        createAuthChallenge,
        verifyAuthChallengeResponse: verifyAuthChallenge,
      },
    });

    // User Pool Client (for CP and Admin apps)
    this.userPoolClient = this.userPool.addClient('AutoMindAppClient', {
      userPoolClientName: 'automind-app-client',
      authFlows: {
        custom: true,
        userSrp: false,
        userPassword: false,
      },
      preventUserExistenceErrors: true,
      accessTokenValidity: cdk.Duration.hours(24),
      idTokenValidity: cdk.Duration.hours(24),
      refreshTokenValidity: cdk.Duration.days(30),
    });

    // =========================================================================
    // API Gateway WebSocket API
    // =========================================================================
    this.websocketApi = new apigatewayv2.CfnApi(this, 'WebSocketApi', {
      name: 'automind-websocket',
      protocolType: 'WEBSOCKET',
      routeSelectionExpression: '$request.body.action',
      description: 'AutoMind AI WebSocket API for chat streaming and real-time updates',
    });

    // WebSocket stage
    const wsStage = new apigatewayv2.CfnStage(this, 'WebSocketStage', {
      apiId: this.websocketApi.ref,
      stageName: 'prod',
      autoDeploy: true,
      defaultRouteSettings: {
        throttlingBurstLimit: 100,
        throttlingRateLimit: 50,
      },
    });

    // Placeholder integration (will be wired to Fargate/Lambda later)
    // For now, create a mock integration so the API can be deployed
    const mockIntegration = new apigatewayv2.CfnIntegration(this, 'MockIntegration', {
      apiId: this.websocketApi.ref,
      integrationType: 'MOCK',
      requestTemplates: {
        '200': '{"statusCode": 200}',
      },
      templateSelectionExpression: '200',
    });

    // $connect route
    new apigatewayv2.CfnRoute(this, 'ConnectRoute', {
      apiId: this.websocketApi.ref,
      routeKey: '$connect',
      authorizationType: 'NONE', // Will add JWT authorizer when wiring to Fargate
      target: `integrations/${mockIntegration.ref}`,
    });

    // $disconnect route
    new apigatewayv2.CfnRoute(this, 'DisconnectRoute', {
      apiId: this.websocketApi.ref,
      routeKey: '$disconnect',
      target: `integrations/${mockIntegration.ref}`,
    });

    // chat route
    new apigatewayv2.CfnRoute(this, 'ChatRoute', {
      apiId: this.websocketApi.ref,
      routeKey: 'chat',
      target: `integrations/${mockIntegration.ref}`,
    });

    // room_navigate route
    new apigatewayv2.CfnRoute(this, 'RoomNavigateRoute', {
      apiId: this.websocketApi.ref,
      routeKey: 'room_navigate',
      target: `integrations/${mockIntegration.ref}`,
    });

    // =========================================================================
    // Outputs
    // =========================================================================
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: this.userPool.userPoolId,
      description: 'Cognito User Pool ID',
      exportName: 'AutoMind-UserPoolId',
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: this.userPoolClient.userPoolClientId,
      description: 'Cognito User Pool Client ID',
      exportName: 'AutoMind-UserPoolClientId',
    });

    new cdk.CfnOutput(this, 'UserPoolArn', {
      value: this.userPool.userPoolArn,
      description: 'Cognito User Pool ARN',
      exportName: 'AutoMind-UserPoolArn',
    });

    new cdk.CfnOutput(this, 'WebSocketApiId', {
      value: this.websocketApi.ref,
      description: 'WebSocket API ID',
      exportName: 'AutoMind-WebSocketApiId',
    });

    new cdk.CfnOutput(this, 'WebSocketUrl', {
      value: `wss://${this.websocketApi.ref}.execute-api.${this.region}.amazonaws.com/prod`,
      description: 'WebSocket URL',
      exportName: 'AutoMind-WebSocketUrl',
    });
  }
}
