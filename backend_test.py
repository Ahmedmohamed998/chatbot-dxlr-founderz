#!/usr/bin/env python3
"""
WhatsApp AI Chatbot Platform - Backend API Testing
Tests all endpoints including auth, chats, templates, campaigns, and AI services
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class WhatsAppAPITester:
    def __init__(self, base_url="https://whatsapp-ai-bot-38.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if details:
            print(f"    {details}")

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        
        # Default headers
        req_headers = {'Content-Type': 'application/json'}
        if self.token:
            req_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            req_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=req_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers, timeout=30)
            else:
                self.log_test(name, False, f"Unsupported method: {method}")
                return False, {}

            success = response.status_code == expected_status
            response_data = {}
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}

            details = f"Status: {response.status_code} (expected {expected_status})"
            if not success:
                details += f", Response: {response.text[:200]}"
            
            self.log_test(name, success, details)
            return success, response_data

        except Exception as e:
            self.log_test(name, False, f"Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        return self.run_test("Health Check", "GET", "health", 200)

    def test_login(self, username: str = "admin", password: str = "Admin123!"):
        """Test login and store token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"username": username, "password": password}
        )
        
        if success and 'token' in response:
            self.token = response['token']
            self.log_test("Token Storage", True, f"Token received and stored")
            return True
        else:
            self.log_test("Token Storage", False, "No token in response")
            return False

    def test_get_user_info(self):
        """Test getting current user info"""
        return self.run_test("Get User Info", "GET", "auth/me", 200)

    def test_get_chats(self):
        """Test getting chat list"""
        return self.run_test("Get Chats", "GET", "chats", 200)

    def test_send_message(self, phone: str = "+1234567890"):
        """Test sending a message to create a conversation"""
        success, response = self.run_test(
            "Send Message (Create Chat)",
            "POST",
            f"chats/{phone}/send",
            200,
            data={"text": "Test message from API testing"}
        )
        return success, response

    def test_get_chat_messages(self, phone: str = "+1234567890"):
        """Test getting messages for a chat"""
        return self.run_test("Get Chat Messages", "GET", f"chats/{phone}/messages", 200)

    def test_toggle_ai(self, phone: str = "+1234567890"):
        """Test toggling AI for a chat"""
        # First pause AI
        success1, _ = self.run_test(
            "Toggle AI (Pause)",
            "PUT",
            f"chats/{phone}/toggle-ai",
            200,
            data={"is_paused": True}
        )
        
        # Then resume AI
        success2, _ = self.run_test(
            "Toggle AI (Resume)",
            "PUT",
            f"chats/{phone}/toggle-ai",
            200,
            data={"is_paused": False}
        )
        
        return success1 and success2

    def test_get_templates(self):
        """Test getting templates"""
        return self.run_test("Get Templates", "GET", "templates", 200)

    def test_webhook_verification(self):
        """Test webhook verification"""
        # Test with correct token
        success, _ = self.run_test(
            "Webhook Verification",
            "GET",
            "webhook?hub.mode=subscribe&hub.verify_token=whatsapp-verify-token&hub.challenge=12345",
            200
        )
        return success

    def test_ai_ingest(self):
        """Test AI knowledge ingestion"""
        test_content = """
        Welcome to our WhatsApp AI chatbot service! 
        We provide automated customer support and can help with:
        - Product information
        - Order status
        - General inquiries
        - Technical support
        
        Our AI is powered by advanced language models and can understand context.
        """
        
        return self.run_test(
            "AI Knowledge Ingest",
            "POST",
            "ai/ingest",
            200,
            data={
                "text_content": test_content,
                "metadata": {"source": "api_test", "type": "support_info"}
            }
        )

    def test_ai_chat(self):
        """Test AI chat endpoint"""
        return self.run_test(
            "AI Chat Response",
            "POST",
            "ai/chat",
            200,
            data={
                "phone_number": "+1234567890",
                "incoming_message_text": "Hello, can you help me?",
                "message_history": [
                    {"role": "user", "content": "Hi there"},
                    {"role": "assistant", "content": "Hello! How can I help you today?"}
                ]
            }
        )

    def test_campaign_send(self):
        """Test campaign sending (will likely fail due to no approved templates)"""
        return self.run_test(
            "Send Campaign",
            "POST",
            "campaigns/send",
            404,  # Expecting 404 since no templates exist
            data={
                "template_name": "test_template",
                "target_phone_numbers": ["+1234567890", "+0987654321"]
            }
        )

    def test_invalid_auth(self):
        """Test endpoints without authentication"""
        # Store current token
        original_token = self.token
        self.token = None
        
        success, _ = self.run_test("Unauthorized Access", "GET", "chats", 401)
        
        # Restore token
        self.token = original_token
        return success

    def test_invalid_login(self):
        """Test login with wrong credentials"""
        return self.run_test(
            "Invalid Login",
            "POST",
            "auth/login",
            401,
            data={"username": "wrong", "password": "wrong"}
        )

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting WhatsApp AI Chatbot API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)

        # Basic connectivity
        self.test_health_check()
        
        # Authentication tests
        self.test_invalid_login()
        if not self.test_login():
            print("❌ Login failed - stopping tests")
            return False
        
        self.test_get_user_info()
        self.test_invalid_auth()
        
        # Chat management tests
        self.test_get_chats()
        phone_test = "+1234567890"
        success, _ = self.test_send_message(phone_test)
        if success:
            self.test_get_chat_messages(phone_test)
            self.test_toggle_ai(phone_test)
        
        # Template and campaign tests
        self.test_get_templates()
        self.test_campaign_send()  # Expected to fail
        
        # Webhook tests
        self.test_webhook_verification()
        
        # AI service tests
        self.test_ai_ingest()
        self.test_ai_chat()
        
        return True

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        # Show failed tests
        failed_tests = [r for r in self.test_results if not r['success']]
        if failed_tests:
            print(f"\n❌ Failed Tests ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
        
        print("\n✅ All critical endpoints tested!")
        return self.tests_passed == self.tests_run

def main():
    """Main test execution"""
    tester = WhatsAppAPITester()
    
    try:
        success = tester.run_all_tests()
        tester.print_summary()
        
        # Save detailed results
        with open('/app/test_reports/backend_api_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': tester.tests_run,
                    'passed': tester.tests_passed,
                    'failed': tester.tests_run - tester.tests_passed,
                    'success_rate': tester.tests_passed/tester.tests_run*100 if tester.tests_run > 0 else 0
                },
                'results': tester.test_results,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())