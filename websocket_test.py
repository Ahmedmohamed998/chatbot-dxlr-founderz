#!/usr/bin/env python3
"""
WebSocket Testing for WhatsApp AI Chatbot Platform
Tests WebSocket connectivity and real-time message broadcasting
"""

import asyncio
import websockets
import json
import requests
from datetime import datetime

class WebSocketTester:
    def __init__(self, base_url="https://whatsapp-ai-bot-38.preview.emergentagent.com"):
        self.base_url = base_url
        self.ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://') + '/api/ws'
        self.token = None
        self.test_results = []

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
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

    def login(self):
        """Login to get auth token"""
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": "admin", "password": "Admin123!"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                self.log_test("Login for WebSocket Test", True, "Token obtained")
                return True
            else:
                self.log_test("Login for WebSocket Test", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Login for WebSocket Test", False, f"Error: {str(e)}")
            return False

    async def test_websocket_connection(self):
        """Test basic WebSocket connection"""
        try:
            print(f"🔌 Connecting to WebSocket: {self.ws_url}")
            
            async with websockets.connect(self.ws_url) as websocket:
                self.log_test("WebSocket Connection", True, "Successfully connected")
                
                # Test ping/pong
                await websocket.send("ping")
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                
                if response == "pong":
                    self.log_test("WebSocket Ping/Pong", True, "Heartbeat working")
                else:
                    self.log_test("WebSocket Ping/Pong", False, f"Unexpected response: {response}")
                
                return True
                
        except asyncio.TimeoutError:
            self.log_test("WebSocket Connection", False, "Connection timeout")
            return False
        except Exception as e:
            self.log_test("WebSocket Connection", False, f"Error: {str(e)}")
            return False

    async def test_websocket_message_broadcast(self):
        """Test WebSocket message broadcasting when sending a message"""
        if not self.token:
            self.log_test("WebSocket Message Broadcast", False, "No auth token available")
            return False

        try:
            print(f"🔌 Testing WebSocket message broadcast...")
            
            # Connect to WebSocket
            async with websockets.connect(self.ws_url) as websocket:
                self.log_test("WebSocket Connection for Broadcast Test", True, "Connected")
                
                # Send a message via API to trigger broadcast
                test_phone = "+1234567890"
                test_message = f"WebSocket test message at {datetime.now().isoformat()}"
                
                # Send message via HTTP API
                response = requests.post(
                    f"{self.base_url}/api/chats/{test_phone}/send",
                    json={"text": test_message},
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=10
                )
                
                if response.status_code != 200:
                    self.log_test("API Message Send", False, f"Status: {response.status_code}")
                    return False
                
                self.log_test("API Message Send", True, "Message sent via API")
                
                # Wait for WebSocket broadcast
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10)
                    data = json.loads(message)
                    
                    if data.get('type') == 'new_message':
                        msg_data = data.get('data', {})
                        if msg_data.get('text') == test_message:
                            self.log_test("WebSocket Message Broadcast", True, "Received correct broadcast message")
                            return True
                        else:
                            self.log_test("WebSocket Message Broadcast", False, f"Wrong message content: {msg_data.get('text')}")
                            return False
                    else:
                        self.log_test("WebSocket Message Broadcast", False, f"Wrong message type: {data.get('type')}")
                        return False
                        
                except asyncio.TimeoutError:
                    self.log_test("WebSocket Message Broadcast", False, "No broadcast message received within timeout")
                    return False
                except json.JSONDecodeError as e:
                    self.log_test("WebSocket Message Broadcast", False, f"Invalid JSON: {str(e)}")
                    return False
                
        except Exception as e:
            self.log_test("WebSocket Message Broadcast", False, f"Error: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all WebSocket tests"""
        print("🚀 Starting WebSocket Tests")
        print(f"📍 Testing WebSocket: {self.ws_url}")
        print("=" * 60)

        # Login first
        if not self.login():
            print("❌ Login failed - stopping WebSocket tests")
            return False

        # Test basic connection
        connection_success = await self.test_websocket_connection()
        
        # Test message broadcasting
        if connection_success:
            await self.test_websocket_message_broadcast()

        return True

    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['success'])
        
        print("\n" + "=" * 60)
        print("📊 WEBSOCKET TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0.0%")
        
        # Show failed tests
        failed_tests = [r for r in self.test_results if not r['success']]
        if failed_tests:
            print(f"\n❌ Failed Tests ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
        
        return passed_tests == total_tests

async def main():
    """Main test execution"""
    tester = WebSocketTester()
    
    try:
        await tester.run_all_tests()
        success = tester.print_summary()
        
        # Save results
        with open('/app/test_reports/websocket_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': len(tester.test_results),
                    'passed': sum(1 for r in tester.test_results if r['success']),
                    'failed': sum(1 for r in tester.test_results if not r['success']),
                },
                'results': tester.test_results,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  WebSocket tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))