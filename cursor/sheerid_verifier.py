"""SheerID Student Verification Program (Cursor.com)"""
import re
import random
import logging
import httpx
from typing import Dict, Optional, Tuple

from . import config
from .name_generator import NameGenerator, generate_email, generate_birth_date
from .img_generator import generate_psu_email, generate_image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class SheerIDVerifier:
    """SheerID Student Identity Verifier (Cursor.com)"""

    def __init__(self, verification_id: str, proxy: Optional[str] = None):
        self.verification_id = verification_id
        self.device_fingerprint = self._generate_device_fingerprint()
        # Support optional proxy for environments with network restrictions
        client_kwargs = {"timeout": 30.0}
        if proxy:
            # httpx uses 'proxy' parameter (singular), not 'proxies'
            client_kwargs["proxy"] = proxy
        self.http_client = httpx.Client(**client_kwargs)

    def __del__(self):
        if hasattr(self, "http_client"):
            self.http_client.close()

    @staticmethod
    def _generate_device_fingerprint() -> str:
        chars = '0123456789abcdef'
        return ''.join(random.choice(chars) for _ in range(32))

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL (keep as-is)"""
        return url

    @staticmethod
    def parse_verification_id(url: str) -> Optional[str]:
        """Parse verificationId or userId parameter"""
        # First try to match verificationId
        match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # If no verificationId, try to match userId (cursor.com uses this format)
        match = re.search(r"userId=([^&]+)", url, re.IGNORECASE)
        if match:
            # userId itself is not verificationId, need to create one via API
            # Return None to let caller know a new verification needs to be created
            return None
        
        return None
    
    @staticmethod
    def parse_user_id(url: str) -> Optional[str]:
        """Parse userId parameter (cursor.com specific)"""
        match = re.search(r"userId=([^&]+)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    
    def create_verification(self, user_id: Optional[str] = None) -> str:
        """Create new verificationId via programId"""
        body = {
            "programId": config.PROGRAM_ID,
        }
        
        # If userId exists, add it to the request
        if user_id:
            body["metadata"] = {
                "userId": user_id
            }
        
        try:
            data, status = self._sheerid_request(
                "POST", f"{config.MY_SHEERID_URL}/rest/v2/verification/", body
            )
            if status != 200 or not isinstance(data, dict) or not data.get("verificationId"):
                raise Exception(f"Failed to create verification (Status码 {status}): {data}")
            
            self.verification_id = data["verificationId"]
            logger.info(f"✅ Got verificationId: {self.verification_id}")
            return self.verification_id
        except Exception as e:
            logger.error(f"Failed to create verification: {e}")
            raise

    def _sheerid_request(
        self, method: str, url: str, body: Optional[Dict] = None
    ) -> Tuple[Dict, int]:
        """发送 SheerID API 请求"""
        headers = {
            "Content-Type": "application/json",
        }

        try:
            response = self.http_client.request(
                method=method, url=url, json=body, headers=headers
            )
            try:
                data = response.json()
            except Exception:
                data = response.text
            return data, response.status_code
        except Exception as e:
            logger.error(f"SheerID request failed: {e}")
            raise

    def _upload_to_s3(self, upload_url: str, img_data: bytes) -> bool:
        """上传 PNG 到 S3"""
        try:
            headers = {"Content-Type": "image/png"}
            response = self.http_client.put(
                upload_url, content=img_data, headers=headers, timeout=60.0
            )
            return 200 <= response.status_code < 300
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return False

    def verify(
        self,
        first_name: str = None,
        last_name: str = None,
        email: str = None,
        birth_date: str = None,
        school_id: str = None,
    ) -> Dict:
        """Execute verification flow, remove status polling to reduce time"""
        try:
            current_step = "initial"

            if not first_name or not last_name:
                name = NameGenerator.generate()
                first_name = name["first_name"]
                last_name = name["last_name"]

            school_id = school_id or config.DEFAULT_SCHOOL_ID
            school = config.SCHOOLS[school_id]

            if not email:
                email = generate_psu_email(first_name, last_name)
            if not birth_date:
                birth_date = generate_birth_date()

            logger.info(f"Student info: {first_name} {last_name}")
            logger.info(f"Email: {email}")
            logger.info(f"School: {school['name']}")
            logger.info(f"Birth date: {birth_date}")
            logger.info(f"Verification ID: {self.verification_id}")

            # Generate student ID card PNG
            logger.info("Step 1/4: Generate student ID card PNG...")
            img_data = generate_image(first_name, last_name, school_id)
            file_size = len(img_data)
            logger.info(f"✅ PNG size: {file_size / 1024:.2f}KB")

            # Submit Student info
            logger.info("Step 2/4: Submit Student info...")
            step2_body = {
                "firstName": first_name,
                "lastName": last_name,
                "birthDate": birth_date,
                "email": email,
                "phoneNumber": "",
                "organization": {
                    "id": int(school_id),
                    "idExtended": school["idExtended"],
                    "name": school["name"],
                },
                "deviceFingerprintHash": self.device_fingerprint,
                "locale": "en-US",
                "metadata": {
                    "marketConsentValue": False,
                    "refererUrl": f"{config.SHEERID_BASE_URL}/verify/{config.PROGRAM_ID}/?verificationId={self.verification_id}",
                    "verificationId": self.verification_id,
                    "flags": '{"collect-info-step-email-first":"default","doc-upload-considerations":"default","doc-upload-may24":"default","doc-upload-redesign-use-legacy-message-keys":false,"docUpload-assertion-checklist":"default","font-size":"default","include-cvec-field-france-student":"not-labeled-optional"}',
                    "submissionOptIn": "By submitting the personal information above, I acknowledge that my personal information is being collected under the privacy policy of the business from which I am seeking a discount",
                },
            }

            step2_data, step2_status = self._sheerid_request(
                "POST",
                f"{config.SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/collectStudentPersonalInfo",
                step2_body,
            )

            if step2_status != 200:
                raise Exception(f"Step 2 Failed (Status码 {step2_status}): {step2_data}")
            if step2_data.get("currentStep") == "error":
                error_msg = ", ".join(step2_data.get("errorIds", ["Unknown error"]))
                raise Exception(f"Step 2 错误: {error_msg}")

            logger.info(f"✅ Step 2 completed: {step2_data.get('currentStep')}")
            current_step = step2_data.get("currentStep", current_step)

            # Skip SSO (if needed)
            if current_step in ["sso", "collectStudentPersonalInfo"]:
                logger.info("Step 3/4: Skip SSO verification...")
                step3_data, _ = self._sheerid_request(
                    "DELETE",
                    f"{config.SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/sso",
                )
                logger.info(f"✅ Step 3 completed: {step3_data.get('currentStep')}")
                current_step = step3_data.get("currentStep", current_step)

            # Log current step before document upload
            logger.info(f"Current step before docUpload: {current_step}")
            
            # Upload document and complete submission
            logger.info("Step 4/4: Request and upload document...")
            step4_body = {
                "files": [
                    {"fileName": "student_card.png", "mimeType": "image/png", "fileSize": file_size}
                ]
            }
            step4_data, step4_status = self._sheerid_request(
                "POST",
                f"{config.SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/docUpload",
                step4_body,
            )
            
            # Check status and log detailed error
            if step4_status != 200:
                error_msg = step4_data.get("message", str(step4_data)) if isinstance(step4_data, dict) else str(step4_data)
                logger.error(f"Step 4 failed with status {step4_status}: {error_msg}")
                logger.error(f"Current step before upload: {current_step}")
                raise Exception(f"Failed to get upload URL (Status {step4_status}): {error_msg}")
            
            if not step4_data.get("documents"):
                logger.error(f"No documents in response: {step4_data}")
                raise Exception("Failed to obtain upload URL")

            upload_url = step4_data["documents"][0]["uploadUrl"]
            logger.info("✅ Get upload URL success")
            if not self._upload_to_s3(upload_url, img_data):
                raise Exception("S3 upload failed")
            logger.info("✅ Student ID card uploaded successfully")

            step6_data, _ = self._sheerid_request(
                "POST",
                f"{config.SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/completeDocUpload",
            )
            logger.info(f"✅ Document submission completed: {step6_data.get('currentStep')}")
            final_status = step6_data

            # 不做Status轮询，直接返回等待审核
            return {
                "success": True,
                "pending": True,
                "message": "Document submitted, awaiting review",
                "verification_id": self.verification_id,
                "redirect_url": final_status.get("redirectUrl"),
                "status": final_status,
            }

        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return {"success": False, "message": str(e), "verification_id": self.verification_id}


def main():
    """Main function - Command line interface"""
    import sys
    import os

    print("=" * 60)
    print("SheerID Student Identity Verification Tool - Cursor.com (Python版)")
    print("=" * 60)
    print()

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Please enter SheerID verification URL: ").strip()

    if not url:
        print("❌ Error: URL not provided")
        sys.exit(1)

    # Support optional proxy via environment variable
    proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
    if proxy:
        print(f"🔧 Using proxy: {proxy}")
        print()

    verification_id = SheerIDVerifier.parse_verification_id(url)
    user_id = SheerIDVerifier.parse_user_id(url)
    
    verifier = SheerIDVerifier(verification_id or "", proxy=proxy)
    
    if not verification_id and user_id:
        print(f"✅ Parsed userId: {user_id}")
        print("⚙️ Creating new verification...")
        try:
            verification_id = verifier.create_verification(user_id)
            print(f"✅ Created verificationId: {verification_id}")
        except Exception as e:
            print(f"❌ Creation failed: {e}")
            sys.exit(1)
    elif verification_id:
        print(f"✅ 解析到Verification ID: {verification_id}")
    else:
        print("❌ 错误: 无效的Verification ID 或 userId 格式")
        sys.exit(1)

    print()

    result = verifier.verify()

    print()
    print("=" * 60)
    print("Verification Result:")
    print("=" * 60)
    print(f"Status: {'✅ Success' if result['success'] else '❌ Failed'}")
    print(f"Message: {result['message']}")
    if result.get("redirect_url"):
        print(f"Redirect URL: {result['redirect_url']}")
    print("=" * 60)

    return 0 if result["success"] else 1


if __name__ == "__main__":
    exit(main())
