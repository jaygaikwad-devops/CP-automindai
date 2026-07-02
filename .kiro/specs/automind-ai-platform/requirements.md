# Requirements Document

## Introduction

AutoMind AI Platform is a multi-tenant SaaS platform for real estate Channel Partners (CPs) and brokers. CPs log in, select a builder's project, generate shareable AI virtual tours, and receive real-time hot-lead alerts when a buyer shows high purchase intent while interacting with "Priya" — an illustrated AI sales avatar. The platform covers the full lifecycle from CP onboarding through buyer engagement to lead conversion tracking.

## Glossary

- **CP**: Channel Partner — a real estate broker or agent who uses the platform to generate and share virtual tours
- **Buyer**: An anonymous end-user who views a virtual tour via a shared link
- **Priya**: An illustrated SVG AI sales avatar that narrates tours and answers buyer questions via RAG-powered chat
- **Builder**: A real estate developer whose projects are listed on the platform
- **Project**: A specific real estate development (building/complex) listed by a Builder
- **Tour**: An AI-generated room-by-room virtual walkthrough of a Project
- **Hot_Lead**: A Buyer whose engagement score reaches or exceeds the alert threshold of 7
- **Lead_Score**: A numeric value (0–10) representing a Buyer's purchase intent based on engagement signals
- **Session**: An anonymous browsing instance for a Buyer viewing a tour
- **RERA_ID**: Real Estate Regulatory Authority registration identifier for a CP
- **RAG**: Retrieval-Augmented Generation — AI technique combining knowledge retrieval with LLM response generation
- **Tour_Script**: A structured JSON document describing room sequence, narration text, and visual assets for a tour
- **Alert_Threshold**: The Lead_Score value (7) at which a CP notification is triggered
- **Knowledge_Base**: AWS Bedrock Knowledge Base containing project-specific information for Priya's Q&A
- **Processing_Pipeline**: The sequence of Lambda workers that transform raw assets into a deployable tour
- **Platform**: The AutoMind AI Platform system as a whole
- **Auth_Service**: The authentication subsystem handling CP OTP login and Buyer anonymous sessions
- **Lead_Engine**: The subsystem responsible for scoring Buyer engagement and triggering alerts
- **Tour_Generator**: The subsystem that processes raw assets into structured Tour_Scripts
- **Avatar_Component**: The frontend SVG component rendering Priya with CSS-driven animations
- **Admin**: An internal AutoMind AI team member who manages Builder onboarding and project creation through an internal dashboard, not the public CP/Buyer flow

## Requirements

### Requirement 1: CP Authentication via OTP

**User Story:** As a CP, I want to log in using my phone number with OTP verification, so that I can securely access my dashboard without remembering passwords.

#### Acceptance Criteria

1. WHEN a CP submits a valid 10-digit Indian mobile phone number, THE Auth_Service SHALL send a 6-digit numeric one-time password to that phone number via SMS within 5 seconds
2. WHEN a CP submits a correct OTP within the validity window, THE Auth_Service SHALL authenticate the CP and issue a session token with a 24-hour expiry
3. IF an incorrect OTP is submitted 3 consecutive times, THEN THE Auth_Service SHALL lock the phone number for 15 minutes and display a lockout message indicating the remaining wait time
4. IF the OTP validity window of 5 minutes expires, THEN THE Auth_Service SHALL invalidate the OTP and require the CP to request a new one
5. WHEN a CP authenticates for the first time, THE Auth_Service SHALL prompt for RERA_ID and name to complete profile registration, and SHALL validate the RERA_ID format before accepting submission
6. IF the SMS delivery fails, THEN THE Auth_Service SHALL retry delivery once after 5 seconds and display an error message indicating SMS delivery failure if the retry also fails
7. IF a phone number requests more than 5 OTPs within a 15-minute window, THEN THE Auth_Service SHALL reject the request and display a rate-limit message indicating the remaining cooldown time
8. IF a CP submits a phone number that is not a valid 10-digit Indian mobile number, THEN THE Auth_Service SHALL reject the submission and display an error message indicating the expected phone number format

### Requirement 2: CP Dashboard

**User Story:** As a CP, I want to view my performance stats and hot leads on a dashboard, so that I can prioritize follow-ups and track my effectiveness.

#### Acceptance Criteria

1. WHEN a CP navigates to the dashboard, THE Platform SHALL display total tours shared, total leads generated, total hot leads, and conversion count for the current month, where a conversion is defined as a lead that reached the visit_booked classification (score 10 or visit_booking_clicked)
2. WHEN a CP navigates to the dashboard, THE Platform SHALL display a list of up to 50 hot leads sorted by Lead_Score in descending order
3. WHEN a new Hot_Lead is detected, THE Platform SHALL update the dashboard hot leads list within 3 seconds via WebSocket push
4. WHEN a CP selects a lead from the list, THE Platform SHALL display the lead detail including buyer name, buyer phone, project name, Lead_Score, a list of triggered signals with their individual score contributions, and a chronologically ordered list of session events with timestamps
5. IF a CP has no leads or tours for the current month, THEN THE Platform SHALL display the dashboard with all metric counts as zero and an empty hot leads list with a message indicating no hot leads are available

### Requirement 3: Project Selection

**User Story:** As a CP, I want to browse and select from available builder projects, so that I can generate shareable tours for properties I am promoting.

#### Acceptance Criteria

1. WHEN a CP navigates to the project selection screen, THE Platform SHALL display all Projects assigned to that CP's builder partnerships
2. THE Platform SHALL display each Project with its name, builder name, location, unit types, and tour availability status (one of: tour_ready, processing_in_progress, processing_failed, or not_started)
3. WHEN a CP selects a Project with a tour availability status of tour_ready, THE Platform SHALL navigate to the share link generation screen
4. WHEN a CP selects a Project with a tour availability status of processing_in_progress, THE Platform SHALL display a message indicating the tour is being processed with an estimated completion time
5. WHEN a CP selects a Project with a tour availability status of processing_failed, THE Platform SHALL display an error message indicating processing failed and offer a retry option

### Requirement 4: Share Link Generation

**User Story:** As a CP, I want to generate a WhatsApp-shareable link for a project tour, so that I can distribute tours to prospective buyers easily.

#### Acceptance Criteria

1. WHEN a CP requests a share link for a Project, THE Platform SHALL generate a unique URL containing the CP identifier and Project identifier within 2 seconds
2. THE Platform SHALL generate an Open Graph–compliant share card with the Project name, a hero image, and a call-to-action text for WhatsApp previews
3. WHEN a CP taps the WhatsApp share button, THE Platform SHALL invoke the WhatsApp share intent with a pre-composed message containing the Project name, a brief description, and the generated link
4. WHEN a share event occurs, THE Platform SHALL record the share event with the timestamp, CP identifier, Project identifier, and share channel, and associate the generated link with the originating CP for lead attribution
5. IF the Platform fails to generate a share link, THEN THE Platform SHALL display an error message indicating the failure reason and allow the CP to retry the generation

### Requirement 5: Buyer Anonymous Session

**User Story:** As a Buyer, I want to view a virtual tour without logging in, so that I can explore properties without friction.

#### Acceptance Criteria

1. WHEN a Buyer opens a tour link, THE Auth_Service SHALL create an anonymous session with a unique session identifier without requiring login
2. THE Auth_Service SHALL store the session identifier in a browser cookie with a 30-day expiry for return-visit detection
3. WHEN a Buyer returns to the same tour link within 24 hours and the session cookie is present, THE Platform SHALL recognize the returning session and apply the returned_within_24h scoring signal (score +2) to the session
4. WHEN a Buyer clicks the visit booking button or the contact CP button, THE Platform SHALL display a form collecting the Buyer's name and 10-digit Indian mobile phone number, and SHALL validate the phone number format before submission
5. IF the session cookie is unavailable on a return visit, THEN THE Auth_Service SHALL create a new anonymous session

### Requirement 6: AI Virtual Tour Walkthrough

**User Story:** As a Buyer, I want to experience a room-by-room virtual tour narrated by Priya, so that I can understand the property layout and features without visiting in person.

#### Acceptance Criteria

1. WHEN a Buyer enters the walkthrough screen, THE Platform SHALL render the first room using the Tour_Script sequence with SVG/Canvas visuals and CSS transitions within 2 seconds of screen entry
2. WHEN a room is displayed, THE Avatar_Component SHALL narrate the room description with synchronized mouth animation triggered by WebSocket talking_start and talking_end events
3. WHEN a Buyer navigates to the next or previous room, THE Platform SHALL transition between rooms using CSS animations within 300 milliseconds
4. THE Platform SHALL track time spent on each room in whole seconds from the moment the room is displayed until the Buyer navigates away
5. WHEN a Buyer navigates to a room they have previously viewed in the same session, THE Lead_Engine SHALL record a room_revisited event for that room
6. WHEN total tour viewing time exceeds 3 minutes, THE Lead_Engine SHALL apply the time_on_tour_3min_plus scoring signal to the session
7. WHEN a Buyer is viewing the first room in the Tour_Script sequence, THE Platform SHALL disable the previous-room navigation control, and WHEN a Buyer is viewing the last room, THE Platform SHALL disable the next-room navigation control
8. IF the Tour_Script contains no rooms or fails to load, THEN THE Platform SHALL display an error message indicating the tour is unavailable and prevent navigation to the walkthrough

### Requirement 7: Priya Avatar Rendering

**User Story:** As a Buyer, I want to see Priya as a friendly illustrated avatar, so that the tour feels guided and personal.

#### Acceptance Criteria

1. THE Avatar_Component SHALL render Priya as an illustrated SVG face at three size variants: badge (48×48px), header (38×38px), and call-to-action (64×64px), displaying the closed-mouth idle state by default
2. WHILE Priya is speaking, THE Avatar_Component SHALL animate the mouth by alternating the SVG path "d" attribute between closed and open states every 280 milliseconds
3. WHEN a talking_start event is received via WebSocket, THE Avatar_Component SHALL begin mouth animation within 50 milliseconds of event receipt
4. WHEN a talking_end event is received via WebSocket, THE Avatar_Component SHALL stop mouth animation and return to the closed-mouth idle state within 50 milliseconds of event receipt
5. IF no talking_end event is received within 30 seconds after a talking_start event, THEN THE Avatar_Component SHALL stop mouth animation and return to the closed-mouth idle state
6. IF the WebSocket connection is lost while Priya is speaking, THEN THE Avatar_Component SHALL stop mouth animation and return to the closed-mouth idle state
7. WHERE the user's operating system has reduced-motion enabled, THE Avatar_Component SHALL display a static open-mouth state instead of the animated alternation while Priya is speaking

### Requirement 8: Priya RAG-Powered Chat

**User Story:** As a Buyer, I want to ask Priya questions about the property and receive accurate answers, so that I can make informed decisions without contacting a salesperson.

#### Acceptance Criteria

1. WHEN a Buyer sends a chat message of 1 to 500 characters, THE Platform SHALL forward the query to the Bedrock Knowledge_Base for retrieval-augmented generation and begin streaming the response within 5 seconds
2. WHEN the Knowledge_Base returns a response, THE Platform SHALL stream Priya's response token-by-token via WebSocket, delivering the first token within 3 seconds of query submission and completing the full response within 30 seconds
3. WHEN a Buyer asks a question classified as a price question, THE Lead_Engine SHALL apply the price_question_asked signal (score +2) to the session
4. WHEN a Buyer asks a question classified as an EMI question, THE Lead_Engine SHALL apply the emi_question_asked signal (score +3) to the session
5. WHEN a Buyer asks a question classified as a RERA question, THE Lead_Engine SHALL apply the rera_question_asked signal (score +1) to the session
6. WHEN a Buyer asks a question classified as an amenities question, THE Lead_Engine SHALL apply the amenities_question_asked signal (score +1) to the session
7. IF the Knowledge_Base returns no results or a confidence score below the configured relevance threshold for a query, THEN THE Platform SHALL respond with a fallback message indicating the information is unavailable and directing the Buyer to contact the CP
8. IF a Buyer submits an empty message or a message exceeding 500 characters, THEN THE Platform SHALL reject the message and display a validation error indicating the allowed length range
9. IF the Knowledge_Base fails to respond within 10 seconds, THEN THE Platform SHALL display a timeout message to the Buyer and allow the Buyer to retry the query

### Requirement 9: Real-Time Lead Scoring

**User Story:** As a CP, I want buyers to be automatically scored based on their engagement signals, so that I can identify and prioritize high-intent leads.

#### Acceptance Criteria

1. WHEN a session event occurs, THE Lead_Engine SHALL recalculate the Lead_Score by summing all applicable signal weights for that session, starting from an initial score of 0
2. THE Lead_Engine SHALL enforce a maximum Lead_Score of 10 regardless of total accumulated signal weights
3. WHEN a Buyer navigates to a room they have previously viewed, THE Lead_Engine SHALL apply the room_revisited signal at +1 per distinct revisited room up to a maximum contribution of +2
4. THE Lead_Engine SHALL classify leads as: browsing (score 0–3), warm (score 4–6), hot (score 7–9), or visit_booked (visit_booking_clicked regardless of numeric score)
5. THE Lead_Engine SHALL store session events in DynamoDB with a TTL of 30 days
6. WHEN a Buyer clicks the visit booking button, THE Lead_Engine SHALL apply the visit_booking_clicked signal (score +4) to the session
7. THE Lead_Engine SHALL apply each signal type at most once per session except room_revisited, which may apply up to 2 times for distinct rooms
8. WHEN a Buyer returns within 24 hours, THE Lead_Engine SHALL apply the returned_within_24h signal (score +2) to the session

### Requirement 10: Hot Lead Alert to CP

**User Story:** As a CP, I want to receive instant WhatsApp alerts when a buyer shows high purchase intent, so that I can follow up while the buyer is still engaged.

#### Acceptance Criteria

1. WHEN a Buyer's Lead_Score reaches or exceeds the Alert_Threshold of 7, THE Lead_Engine SHALL trigger a hot-lead alert to the associated CP
2. THE Platform SHALL send the hot-lead alert via WhatsApp using the Gupshup API containing: buyer name (or "Anonymous Buyer" if not collected), project name, Lead_Score, a list of triggered signals with their individual point contributions, and buyer phone number (if collected)
3. THE Platform SHALL send the hot-lead alert within 10 seconds of the threshold being crossed
4. THE Platform SHALL send a push notification to the CP's device in addition to the WhatsApp message
5. IF the WhatsApp delivery fails (HTTP 4xx/5xx response or timeout after 10 seconds), THEN THE Platform SHALL retry delivery once after 5 seconds, and if the retry also fails, deliver via SMS using AWS SNS as a fallback channel
6. THE Lead_Engine SHALL send only one alert per session per threshold crossing to prevent duplicate notifications
7. IF the Buyer has not provided contact information, THEN THE alert SHALL include the session identifier and project link instead of buyer phone number

### Requirement 11: AI Processing Pipeline

**User Story:** As an admin, I want raw project assets (images and PDFs) to be automatically processed into structured tour content, so that new projects can go live without manual content creation.

#### Acceptance Criteria

1. WHEN raw assets are uploaded to S3, THE Processing_Pipeline SHALL enqueue a processing job via SQS within 5 seconds and set the project status to processing_in_progress
2. WHEN a processing job is dequeued, THE Processing_Pipeline SHALL execute the image_analyzer worker to tag room images using AWS Rekognition with room type, features, and object labels
3. WHEN a processing job is dequeued, THE Processing_Pipeline SHALL execute the pdf_extractor worker to extract structured data from brochures using AWS Textract and Bedrock
4. WHEN image analysis and PDF extraction have both completed successfully, THE Processing_Pipeline SHALL execute the tour_sequencer worker to build the Tour_Script JSON and Priya narration content
5. WHEN the Tour_Script is built, THE Processing_Pipeline SHALL execute the kb_builder worker to ingest project content into the Bedrock Knowledge_Base
6. WHEN the kb_builder worker completes successfully, THE Processing_Pipeline SHALL set the project status to tour_ready and notify the admin via the platform dashboard within 10 seconds of completion
7. IF any worker in the Processing_Pipeline fails after 3 retry attempts, THEN THE Platform SHALL log the error, mark the project status as processing_failed, and notify the admin via the platform dashboard and email within 30 seconds of the final failure
8. IF the end-to-end processing pipeline does not complete within 15 minutes of job enqueue, THEN THE Platform SHALL mark the project status as processing_timeout, terminate remaining workers, and notify the admin

### Requirement 12: Multi-Tenant Data Isolation

**User Story:** As a platform operator, I want each CP to access only their assigned projects and leads, so that tenant data remains isolated and secure.

#### Acceptance Criteria

1. THE Platform SHALL enforce that a CP can view only Projects associated with their builder partnerships, and SHALL return a 403 Forbidden response for any API request or direct URL access attempting to retrieve a Project not assigned to the requesting CP
2. THE Platform SHALL enforce that a CP can view only leads generated from their own shared links, and SHALL return a 403 Forbidden response for any API request attempting to retrieve leads belonging to another CP
3. WHEN a Buyer opens a tour link containing a CP identifier, THE Platform SHALL associate the resulting session with the CP whose identifier is encoded in that link
4. THE Platform SHALL isolate each Builder's project data such that CPs from one Builder cannot access another Builder's project content, including tour assets, Tour_Scripts, and Knowledge_Base entries
5. IF a Buyer opens a tour link with an invalid or expired CP identifier, THEN THE Platform SHALL display an error page indicating the link is no longer valid and prevent access to the tour

### Requirement 13: Credit-Based Billing

**User Story:** As a CP, I want to purchase credit packs to activate AI tour processing for my projects, so that I pay per project and can manage my budget.

#### Acceptance Criteria

1. THE Platform SHALL offer three credit packs: Starter (₹999 = 2 credits), Growth (₹3,999 = 10 credits), Agency (₹14,999 = 50 credits)
2. WHEN a CP selects a credit pack, THE Platform SHALL create a Razorpay one-time payment order in INR and return the payment link
3. WHEN payment is confirmed by Razorpay webhook (payment.captured event), THE Platform SHALL verify the webhook signature using razorpay.utility.verify_webhook_signature before processing, return 400 if verification fails, and on success atomically add the purchased credits to the CP's credit_balance and record a purchase transaction within 30 seconds
4. WHEN a CP triggers tour processing for a project, THE Platform SHALL check credit_balance >= 1, and IF balance is 0, THEN return 402 Payment Required with the current balance
5. WHEN a CP triggers tour processing with credit_balance >= 1, THE Platform SHALL atomically deduct 1 credit using SELECT FOR UPDATE, record a deduction transaction referencing the project_id in the SAME database transaction (rollback both if either fails), then enqueue the processing pipeline
6. THE Platform SHALL NOT affect existing active projects (tour_ready status) based on credit balance — only new project activation requires credits

### Requirement 14: WhatsApp Share Tracking

**User Story:** As a CP, I want to know when a buyer clicks my shared WhatsApp link, so that I can track engagement from the point of share.

#### Acceptance Criteria

1. WHEN a Buyer clicks a shared tour link, THE Platform SHALL record the click event with timestamp, referrer URL, browser user-agent string, and device type (mobile or desktop)
2. WHEN a Buyer clicks the WhatsApp share button within the tour, THE Lead_Engine SHALL apply the whatsapp_share_clicked signal (score +1) to the session
3. THE Platform SHALL attribute all session activity to the CP whose share link originated the visit
4. IF a Buyer accesses a tour via multiple CP share links, THEN THE Platform SHALL attribute the session to the CP whose link was most recently clicked
5. WHEN a link click event is recorded, THE Platform SHALL make the click data visible to the originating CP on the dashboard within 5 seconds

### Requirement 15: Tour Script Serialization and Parsing

**User Story:** As a developer, I want the tour script format to be reliably serialized and parsed, so that tour content is consistently rendered across all clients.

#### Acceptance Criteria

1. THE Tour_Generator SHALL serialize Tour_Script objects into valid JSON conforming to the tour-script schema, including a schema version identifier in the output document
2. THE Platform SHALL parse Tour_Script JSON of up to 5 MB into Tour_Script objects preserving all fields, nested structures, and values such that every field present in the source JSON is present in the resulting object with an identical value
3. THE Platform SHALL guarantee the round-trip property: for any valid Tour_Script object, serializing to JSON and parsing the result back SHALL produce an object that is deep-equal to the original across all fields and nested values
4. IF a Tour_Script JSON document does not conform to the schema, THEN THE Platform SHALL return a validation error that includes the path of the non-conforming field, the constraint that was violated, and the expected format for that field
5. IF a Tour_Script JSON document contains fields not defined in the tour-script schema, THEN THE Platform SHALL ignore the unrecognized fields during parsing without raising an error and without including them in the resulting Tour_Script object

### Requirement 16: Builder-CP Partnership Management

**User Story:** As an Admin, I want to create Projects and assign CPs to Builders via an internal tool, so that CPs gain access to the correct project data without self-service onboarding.

#### Acceptance Criteria

1. WHEN an Admin creates a new Project in the internal dashboard, THE Platform SHALL store the Project with a unique identifier, Builder association, project name, location, and unit types, and set the project status to not_started
2. WHEN an Admin assigns a CP to a Builder's Project, THE Platform SHALL create a partnership record linking the CP identifier to the Project identifier and Builder identifier, granting the CP read access to that Project's tours and assets
3. WHEN a partnership record is created for a CP and a Project, THE Platform SHALL include that Project in the CP's project selection list within 5 seconds of assignment
4. WHEN an Admin removes a CP from a Builder's Project, THE Platform SHALL revoke the CP's access to that Project immediately, return a 403 Forbidden response for subsequent access attempts by that CP, and remove the Project from the CP's project selection list
5. THE Platform SHALL enforce that only users with the Admin role can create Projects, assign CPs to Projects, or remove CPs from Projects, and SHALL return a 403 Forbidden response for any non-Admin user attempting these operations
6. IF an Admin attempts to assign a CP to a Project that does not exist, THEN THE Platform SHALL reject the assignment and display an error message indicating the Project was not found
7. IF an Admin attempts to assign a CP who is already assigned to the specified Project, THEN THE Platform SHALL reject the duplicate assignment and display a message indicating the CP is already assigned to that Project
8. THE Platform SHALL use the partnership records as the authorization source for the multi-tenant data isolation enforced in Requirement 12, such that a CP can access only Projects for which a valid partnership record exists

### Requirement 17: Project Asset Upload

**User Story:** As an Admin, I want to upload project assets (images, videos, PDFs, and floor plans) on behalf of the Builder, so that the AI Processing Pipeline can generate tour content.

#### Acceptance Criteria

1. WHEN an Admin uploads images for a Project, THE Platform SHALL accept files in JPG or PNG format with a maximum file size of 20 MB per image
2. WHEN an Admin uploads a video for a Project, THE Platform SHALL accept files in MP4 format with a maximum file size of 100 MB per video and a maximum of 3 videos per Project
3. WHEN an Admin uploads a brochure for a Project, THE Platform SHALL accept files in PDF format with a maximum file size of 20 MB per file and a maximum of 5 brochures per Project
4. THE Platform SHALL require a minimum of 10 images and a maximum of 30 images per Project before marking the image upload as complete
5. THE Platform SHALL require exactly one floor plan upload in JPG, PNG, or PDF format with a maximum file size of 20 MB as a mandatory asset before tour processing can begin
6. IF an Admin attempts to initiate tour processing for a Project without a floor plan uploaded, THEN THE Platform SHALL reject the request and display an error message indicating that a floor plan is required before processing can begin
7. IF an Admin uploads a file that exceeds the maximum allowed size for its type, THEN THE Platform SHALL reject the upload and display an error message indicating the maximum allowed size for that file type
8. IF an Admin uploads a file with an unsupported format, THEN THE Platform SHALL reject the upload and display an error message listing the accepted file types for that asset category
9. WHEN an Admin completes all required asset uploads (minimum 10 images and 1 floor plan) for a Project, THE Platform SHALL enable the option to trigger the Processing_Pipeline as defined in Requirement 11
10. WHEN an Admin triggers tour processing after asset upload completion, THE Platform SHALL upload the assets to S3 and initiate the Processing_Pipeline workflow as defined in Requirement 11 within 5 seconds
11. IF an Admin attempts to upload more than 30 images for a Project, THEN THE Platform SHALL reject the upload and display an error message indicating the maximum of 30 images has been reached
12. IF an Admin attempts to upload assets for a Project that is currently in processing_in_progress or tour_ready status, THEN THE Platform SHALL reject the upload and display an error message indicating that assets cannot be modified while the project is in that status
