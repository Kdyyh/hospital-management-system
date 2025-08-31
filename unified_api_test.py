#!/usr/bin/env python3
"""
统一的医院系统API测试脚本
测试所有API端点并报告错误
"""
import requests
import json
import sys
import time
import os
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"

# 测试用户配置
TEST_USERS = {
    "admin": {"username": "admin1", "password": "123456", "role": "admin"},
    "core": {"username": "core1", "password": "123456", "role": "core"}, 
    "super": {"username": "super", "password": "123456", "role": "super"},
    "patient": {"username": "patient1", "password": "123456", "role": "patient"}
}

@dataclass
class TestResult:
    success: bool
    endpoint: str
    method: str
    status_code: int
    response_time: float
    error_message: str = ""
    description: str = ""
    user_role: str = ""

class UnifiedAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {}
        self.current_user = None
        self.current_role = None
        self.test_results = []
        self.error_results = []
        
    def login(self, username: str, password: str, role: str) -> bool:
        """使用指定用户登录"""
        print(f"🔐 正在使用 {username} ({role}) 登录...")
        try:
            start_time = time.time()
            response = self.session.post(
                f"{BASE_URL}/api/auth/login",
                json={"username": username, "password": password},
                headers={"Content-Type": "application/json"}
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                # 使用传统的DRF token
                token = data.get('token')
                self.headers = {
                    "Authorization": f"Token {token}",
                    "Content-Type": "application/json"
                }
                self.current_user = username
                self.current_role = role
                
                result = TestResult(
                    success=True,
                    endpoint="/api/auth/login",
                    method="POST",
                    status_code=response.status_code,
                    response_time=response_time,
                    description=f"{username} 登录成功",
                    user_role=role
                )
                self.test_results.append(result)
                print(f"✅ {username} 登录成功 (响应时间: {response_time:.2f}s)")
                return True
            else:
                result = TestResult(
                    success=False,
                    endpoint="/api/auth/login",
                    method="POST",
                    status_code=response.status_code,
                    response_time=response_time,
                    error_message=response.text[:200],
                    description=f"{username} 登录失败",
                    user_role=role
                )
                self.test_results.append(result)
                self.error_results.append(result)
                print(f"❌ {username} 登录失败: {response.status_code} - {response.text[:100]}")
                return False
        except Exception as e:
            result = TestResult(
                success=False,
                endpoint="/api/auth/login",
                method="POST",
                status_code=0,
                response_time=0,
                error_message=str(e),
                description=f"{username} 登录异常",
                user_role=role
            )
            self.test_results.append(result)
            self.error_results.append(result)
            print(f"❌ {username} 登录异常: {e}")
            return False
    
    def test_endpoint(self, method: str, endpoint: str, data: Dict = None, 
                     expected_status: int = 200, description: str = "") -> TestResult:
        """测试单个API端点"""
        url = f"{BASE_URL}{endpoint}"
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=self.headers)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, headers=self.headers)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, headers=self.headers)
            elif method.upper() == "PATCH":
                response = self.session.patch(url, json=data, headers=self.headers)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, headers=self.headers)
            else:
                error_msg = f"不支持的HTTP方法: {method}"
                result = TestResult(
                    success=False,
                    endpoint=endpoint,
                    method=method,
                    status_code=0,
                    response_time=0,
                    error_message=error_msg,
                    description=description,
                    user_role=self.current_role
                )
                self.test_results.append(result)
                self.error_results.append(result)
                return result
            
            response_time = time.time() - start_time
            
            if response.status_code == expected_status:
                result = TestResult(
                    success=True,
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status_code,
                    response_time=response_time,
                    description=description,
                    user_role=self.current_role
                )
                print(f"✅ {method} {endpoint} - 成功 ({response_time:.2f}s)")
            else:
                result = TestResult(
                    success=False,
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status_code,
                    response_time=response_time,
                    error_message=response.text[:200],
                    description=description,
                    user_role=self.current_role
                )
                print(f"❌ {method} {endpoint} - 失败: {response.status_code} ({response_time:.2f}s)")
                self.error_results.append(result)
                
        except Exception as e:
            response_time = time.time() - start_time
            result = TestResult(
                success=False,
                endpoint=endpoint,
                method=method,
                status_code=0,
                response_time=response_time,
                error_message=str(e),
                description=description,
                user_role=self.current_role
            )
            print(f"❌ {method} {endpoint} - 异常: {e} ({response_time:.2f}s)")
            self.error_results.append(result)
        
        self.test_results.append(result)
        return result
    
    def test_all_apis_for_role(self, role: str):
        """测试特定角色的所有API"""
        user = TEST_USERS[role]
        if not self.login(user["username"], user["password"], role):
            return
        
        print(f"\n🧪 开始测试 {role} 用户角色的所有API...")
        
        # 根据用户角色设置不同的测试用例
        test_cases = []
        
        # 所有用户通用的API
        test_cases.extend([
            ("GET", "/api/user/profile", None, 200, "获取用户资料"),
            ("GET", "/healthz", None, 200, "健康检查"),
        ])
        
        if role in ["admin", "core", "super"]:
            # 管理员权限的API
            test_cases.extend([
                ("POST", "/api/auth/logout", None, 200, "用户登出"),
                ("GET", "/api/departments", None, 200, "获取科室列表"),
                ("GET", "/api/departments/members", None, 200, "获取科室成员"),
                ("GET", "/api/queue/status", None, 200, "获取队列状态"),
                ("GET", "/api/admin/queue/list", None, 200, "获取管理队列"),
                ("GET", "/api/admin/queue/stats", None, 200, "获取队列统计"),
                ("GET", "/api/queue/list", None, 200, "获取队列列表"),
                ("GET", "/api/inquiries", None, 200, "获取咨询列表"),
                ("GET", "/api/tasks", None, 200, "获取任务列表"),
                ("GET", "/api/messages", None, 200, "获取消息列表"),
                ("GET", "/api/ads", None, 200, "获取广告列表"),
                ("GET", "/api/admin/dashboard", None, 200, "获取管理仪表板"),
                ("GET", "/api/groups", None, 200, "获取分组列表"),
                ("GET", "/api/departments/admins", None, 200, "获取科室管理员"),
                ("GET", "/api/patients/export", None, 200, "导出患者数据"),
                ("GET", "/api/admin/profile", None, 200, "获取管理员资料"),
                ("GET", "/api/report/log", None, 200, "获取操作日志"),
                ("GET", "/api/groups/invites", None, 200, "获取邀请列表"),
                ("GET", "/api/groups/transfer-requests", None, 200, "获取转移请求"),
                ("GET", "/api/user/available-departments", None, 200, "获取可用科室"),
            ])
            
            # 只有绑定科室的管理员才能访问患者列表
            if role == "super":
                test_cases.extend([
                    ("GET", "/api/patients", None, 200, "获取患者列表"),
                    ("GET", "/api/departments/configs", None, 200, "获取所有科室配置"),
                    ("GET", "/api/admin/queue/list-all", None, 200, "获取所有管理队列"),
                    ("GET", "/api/tasks/1", None, 200, "获取任务详情"),
                ])
            
            # 只有super可以访问的API
            if role == "super":
                test_cases.extend([
                    ("GET", "/api/kpi/all", None, 200, "获取所有KPI"),
                    ("GET", "/api/kpi/my", None, 200, "获取个人KPI"),
                    ("GET", "/api/kpi/department", None, 200, "获取科室KPI"),
                    ("POST", "/api/groups/create", {"name": "测试科室", "description": "测试描述"}, 200, "创建分组"),
                    ("POST", "/api/groups/unbind", {"userId": 1}, 200, "解除绑定"),
                    ("POST", "/api/user/change-password", {"oldPassword": "123456", "newPassword": "newpass123456"}, 200, "修改密码"),
                    ("POST", "/api/user/bind-department", {"departmentId": "g1"}, 200, "绑定科室"),
                ])
        
        elif role == "patient":
            # 患者权限的API
            test_cases.extend([
                ("POST", "/api/auth/logout", None, 200, "用户登出"),
                ("GET", "/api/departments", None, 200, "获取科室列表"),
                ("GET", "/api/departments/members", None, 200, "获取科室成员"),
                ("GET", "/api/queue/status", None, 200, "获取队列状态"),
                ("GET", "/api/queue/list", None, 200, "获取队列列表"),
                ("GET", "/api/patient/inquiries", None, 200, "获取患者咨询"),
                ("GET", "/api/tasks", None, 200, "获取任务列表"),
                ("GET", "/api/messages", None, 200, "获取消息列表"),
                ("GET", "/api/ads", None, 200, "获取广告列表"),
                ("GET", "/api/kpi/my", None, 200, "获取个人KPI"),
                ("GET", "/api/groups", None, 200, "获取分组列表"),
                ("GET", "/api/patient/messages", None, 200, "获取患者消息"),
                ("GET", "/api/user/check-department-binding", None, 200, "检查科室绑定"),
                ("GET", "/api/user/available-departments", None, 200, "获取可用科室"),
            ])
        
        # 执行所有测试用例
        for method, endpoint, data, expected_status, description in test_cases:
            self.test_endpoint(method, endpoint, data, expected_status, description)
        
        # 测试登出
        self.test_endpoint("POST", "/api/auth/logout", None, 200, "最终用户登出")
        
        print(f"📊 {role} 用户API测试完成")
    
    def run_comprehensive_test(self):
        """运行全面的API测试"""
        print("🏥 医院系统统一API测试")
        print("=" * 50)
        print("测试所有API端点并报告错误情况")
        print("=" * 50)
        
        # 测试所有用户角色
        for role in ["admin", "core", "super", "patient"]:
            self.test_all_apis_for_role(role)
            # 每次测试后重新创建session
            self.session = requests.Session()
            self.headers = {}
            self.current_user = None
            self.current_role = None
        
        # 生成报告
        self.generate_reports()
        
        return len(self.error_results) == 0
    
    def generate_reports(self):
        """生成测试报告"""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # 显示摘要
        print(f"\n🎯 测试完成摘要:")
        print(f"  总测试数: {total_tests}")
        print(f"  成功测试: {successful_tests}")
        print(f"  失败测试: {len(self.error_results)}")
        print(f"  成功率: {success_rate:.1f}%")
        
        # 显示错误详情
        if self.error_results:
            print(f"\n❌ 错误详情 ({len(self.error_results)} 个错误):")
            print("=" * 80)
            for i, error in enumerate(self.error_results, 1):
                print(f"{i}. [{error.user_role}] {error.method} {error.endpoint}")
                print(f"   状态码: {error.status_code}")
                print(f"   错误: {error.error_message}")
                print(f"   描述: {error.description}")
                print("-" * 80)
        
        # 保存详细报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": round(success_rate, 1),
            "errors_count": len(self.error_results),
            "error_details": [
                {
                    "user_role": r.user_role,
                    "endpoint": r.endpoint,
                    "method": r.method,
                    "status_code": r.status_code,
                    "error_message": r.error_message,
                    "description": r.description,
                    "response_time": round(r.response_time, 3)
                }
                for r in self.error_results
            ],
            "all_results": [
                {
                    "user_role": r.user_role,
                    "endpoint": r.endpoint,
                    "method": r.method,
                    "status_code": r.status_code,
                    "success": r.success,
                    "response_time": round(r.response_time, 3),
                    "description": r.description,
                    "error": r.error_message if not r.success else None
                }
                for r in self.test_results
            ]
        }
        
        # report_filename = f"unified_api_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        # with open(report_filename, 'w', encoding='utf-8') as f:
        #     json.dump(report, f, ensure_ascii=False, indent=2)
        
        # print(f"\n📝 详细报告已保存到: {report_filename}")

def cleanup_old_test_files():
    """清理旧的测试文件"""
    files_to_delete = [
        "scripts/quick_test.py",
        "scripts/test_all_apis.py", 
        "scripts/detailed_api_test.py",
        "scripts/improved_api_test.py",
        "api_test_report_*.json"
    ]
    
    print("🧹 清理旧的测试文件...")
    for file_pattern in files_to_delete:
        if os.path.exists(file_pattern):
            if file_pattern.endswith('*.json'):
                # 删除所有JSON报告文件
                import glob
                for json_file in glob.glob(file_pattern):
                    os.remove(json_file)
                    print(f"🗑️  删除: {json_file}")
            else:
                os.remove(file_pattern)
                print(f"🗑️  删除: {file_pattern}")

def main():
    """主函数"""
    # 清理旧文件
    cleanup_old_test_files()
    
    # 运行测试
    tester = UnifiedAPITester()
    
    if tester.run_comprehensive_test():
        print("\n✅ 所有API测试完成，系统功能正常")
        sys.exit(0)
    else:
        print(f"\n⚠️  API测试发现 {len(tester.error_results)} 个问题，请查看错误详情")
        sys.exit(1)

if __name__ == "__main__":
    main()
