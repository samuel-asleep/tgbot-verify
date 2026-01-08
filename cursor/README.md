# Cursor.com SheerID Verification Module

## Overview

This module implements automatic student verification for Cursor.com's education discount program using SheerID's verification service.

## How It Works

### 1. Auto-Verification Process

The bot automates the complete SheerID verification workflow:

1. **URL Parsing**: Extracts verification parameters from the URL
   - Standard format: `verificationId=abc123...`
   - Cursor.com format: `userId=user_01XXXX...`

2. **Session Creation** (for userId format):
   - Automatically creates a SheerID verification session
   - Links the userId to the new verification session

3. **Information Generation**:
   - Generates realistic student names using combinatorial name patterns
   - Creates Penn State University student email addresses
   - Generates random birth dates (2000-2005 range)
   - Creates 9-digit PSU student ID numbers

4. **Document Creation**:
   - Generates HTML mockup of Penn State LionPATH student portal
   - Uses Playwright to render and screenshot the HTML
   - Creates realistic PNG student ID card image

5. **Submission**:
   - Submits student personal information to SheerID API
   - Uploads the generated student ID card to AWS S3
   - Completes the document verification workflow

### 2. URL Format Support

**Standard Format** (with verificationId):
```
https://services.sheerid.com/verify/681044b7729fba7beccd3565/?verificationId=abc123def456
```

**Cursor.com Format** (with userId):
```
https://services.sheerid.com/verify/681044b7729fba7beccd3565/?userId=user_01KDZVSCXKET31E18FNFR1HFFQ
```

The module automatically detects and handles both formats.

### 3. Verification Workflow

```
User submits URL → Parse parameters → Create session (if needed)
    ↓
Generate student info → Create student ID image → Upload to S3
    ↓
Submit to SheerID → Wait for review → Return result to user
```

## Usage

### Command

```
/verify6 <cursor.com_sheerid_url>
```

### Example

```
/verify6 https://services.sheerid.com/verify/681044b7729fba7beccd3565/?userId=user_01KDZVSCXKET31E18FNFR1HFFQ
```

### Response

The bot will:
1. Deduct verification credits from user balance
2. Generate student information and ID card
3. Submit to SheerID for verification
4. Return the verification result with redirect URL

## Configuration

### Program ID

The Cursor.com SheerID program ID is configured in `cursor/config.py`:

```python
PROGRAM_ID = '681044b7729fba7beccd3565'
```

⚠️ **Important**: This ID may change over time. If verification stops working, extract the new program ID from Cursor.com's verification page using browser dev tools.

### Schools

The module uses Pennsylvania State University (Penn State) credentials with multiple campus options configured in `cursor/config.py`.

## Technical Details

### Dependencies

- `httpx`: HTTP client for API requests
- `playwright`: Browser automation for screenshot generation
- `python-telegram-bot`: Telegram bot framework

### File Structure

```
cursor/
├── __init__.py              # Module initialization
├── config.py                # Configuration (program ID, schools)
├── name_generator.py        # Random name generation
├── img_generator.py         # Student ID card generation
└── sheerid_verifier.py      # Main verification logic
```

### API Endpoints

- **Create Verification**: `POST /rest/v2/verification/`
- **Submit Info**: `POST /rest/v2/verification/{id}/step/collectStudentPersonalInfo`
- **Upload Document**: `POST /rest/v2/verification/{id}/step/docUpload`
- **Complete Upload**: `POST /rest/v2/verification/{id}/step/completeDocUpload`

## Differences from Other Verifiers

1. **URL Parameter**: Uses `userId` instead of `verificationId` (though supports both)
2. **Session Creation**: Requires creating a verification session from userId
3. **Student Type**: Student verification (not teacher)
4. **School**: Uses Penn State University credentials

## Security Considerations

- All generated information is fake and randomized
- No real student data is used or stored
- HTTP client has 30-second timeout to prevent hanging
- Proper error handling and credit refunds on failure
- Concurrent verification requests are controlled via semaphores
