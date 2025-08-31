# 医院系统API开发指南

本文档提供了医院系统所有API的详细说明，方便前端开发人员使用。

## 🏥 系统概述

医院管理系统是一个完整的医疗服务平台，提供患者管理、科室管理、队列管理、咨询系统等功能。系统采用RESTful API设计，使用Token认证方式。

## 📋 基础信息

- **基础URL**: `http://127.0.0.1:8000`
- **认证方式**: Token认证 (在Header中添加 `Authorization: Token {token}`)
- **Content-Type**: `application/json`
- **字符编码**: UTF-8
- **API版本**: v1
- **响应格式**: JSON

## 🔐 认证机制

### Token获取流程
1. 用户通过登录接口获取token
2. 在后续请求的Header中携带token: `Authorization: Token {token}`
3. Token有效期为24小时
4. Token过期后需要重新登录获取

### 安全要求
- 所有敏感操作都需要Token认证
- 密码传输必须使用HTTPS加密
- Token需要安全存储，避免泄露

## 🔐 用户认证API

### 用户登录
- **端点**: `POST /api/auth/login`
- **权限**: 无需认证
- **参数**: 
  ```json
  {
    "username": "用户名 (字符串，必填)",
    "password": "密码 (字符串，必填，最小长度6位)"
  }
  ```
- **成功响应 (200)**: 
  ```json
  {
    "ok": true,
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": 1,
      "username": "admin1",
      "email": "admin1@hospital.com",
      "role": "admin",
      "first_name": "Admin1",
      "last_name": "医生",
      "group": {
        "id": "g1",
        "name": "内科"
      }
    }
  }
  ```
- **失败响应 (400)**: 
  ```json
  {
    "ok": false,
    "error": {
      "code": "validation_error",
      "message": "用户名或密码错误"
    }
  }
  ```
- **失败响应 (500)**: 
  ```json
  {
    "ok": false,
    "error": {
      "code": "server_error",
      "message": "服务器内部错误"
    }
  }
  ```
- **注意事项**:
  - 密码错误3次后会暂时锁定账号5分钟
  - Token有效期为24小时
  - 建议在前端实现自动重试机制

### 用户登出
- **端点**: `POST /api/auth/logout`
- **权限**: 需要认证
- **参数**: 无
- **成功响应 (200)**: 
  ```json
  {
    "ok": true,
    "message": "登出成功"
  }
  ```
- **失败响应 (401)**: 
  ```json
  {
    "ok": false,
    "error": {
      "code": "authentication_failed",
      "message": "认证失败"
    }
  }
  ```
- **功能说明**: 使当前token失效，无法再用于API调用

### 修改密码
- **端点**: `POST /api/user/change-password`
- **权限**: 需要认证
- **参数**:
  ```json
  {
    "oldPassword": "旧密码 (字符串，必填)",
    "newPassword": "新密码 (字符串，必填，最小长度8位，需包含字母和数字)"
  }
  ```
- **成功响应 (200)**: 
  ```json
  {
    "ok": true,
    "message": "密码修改成功"
  }
  ```
- **失败响应 (400)**: 
  ```json
  {
    "ok": false,
    "error": {
      "code": "validation_error",
      "message": "新密码不符合安全要求"
    }
  }
  ```
- **失败响应 (401)**: 
  ```json
  {
    "ok": false,
    "error": {
      "code": "authentication_failed", 
      "message": "旧密码不正确"
    }
  }
  ```
- **安全要求**:
  - 新密码不能与旧密码相同
  - 密码需要包含大小写字母和数字
  - 建议定期更换密码


## 👥 用户管理API

### 获取用户资料
- **端点**: `GET /api/user/profile`
- **权限**: 所有认证用户
- **参数**: 无
- **成功响应 (200)**: 
  ```json
  {
    "ok": true,
    "user": {
      "id": 1,
      "username": "admin1",
      "email": "admin1@hospital.com",
      "role": "admin",
      "first_name": "Admin1",
      "last_name": "医生",
      "phone": "13800138000",
      "group": {
        "id": "g1",
        "name": "内科"
      },
      "created_at": "2024-01-15T10:30:00Z",
      "last_login": "2024-01-20T14:25:00Z"
    }
  }
  ```
- **失败响应 (401)**: 
  ```json
  {
    "ok": false,
    "error": {
      "code": "authentication_failed",
      "message": "认证失败"
    }
  }
  ```

### 更新用户资料
- **端点**: `POST /api/user/profile/update`
- **权限**: 需要认证
- **参数**:
  ```json
  {
    "first_name": "名字 (字符串，可选)",
    "last_name": "姓氏 (字符串，可选)", 
    "email": "邮箱 (字符串，可选，需符合邮箱格式)",
    "phone": "电话号码 (字符串，可选)"
  }
  ```
- **成功响应 (200)**: 
  ```json
  {
    "ok": true,
    "message": "用户资料更新成功",
    "user": {更新后的用户信息}
  }
  ```
- **失败响应 (400)**: 
  ```json
  {
    "ok": false,
    "error": {
      "code": "validation_error",
      "message": "邮箱格式不正确"
    }
  }
  ```

### 用户注册
- **端点**: `POST /api/user/register`
- **权限**: 无需认证
- **参数**:
  ```json
  {
    "username": "用户名 (字符串，必填，3-20字符，只能包含字母数字和下划线)",
    "password": "密码 (字符串，必填，最小8位，需包含字母和数字)",
    "role": "用户角色 (字符串，必填，可选值: patient, admin, core, super)",
    "email": "邮箱 (字符串，可选)",
    "first_name": "名字 (字符串，可选)",
    "last_name": "姓氏 (字符串，可选)"
  }
  ```
- **成功响应 (201)**: 
  ```json
  {
    "ok": true,
    "message": "用户注册成功",
    "user": {
      "id": 123,
      "username": "newuser",
      "role": "patient"
    }
  }
  ```
- **失败响应 (400)**: 
  ```json
  {
    "ok": false,
    "error": {
      "code": "validation_error",
      "message": "用户名已存在"
    }
  }
  ```
- **注意事项**:
  - 用户名必须唯一
  - 密码需要符合安全策略
  - 注册后需要管理员审核才能激活（如角色为admin/core）

## 科室/部门管理API

### 获取科室列表
- **端点**: `GET /api/departments`
- **权限**: 所有认证用户

### 获取科室成员
- **端点**: `GET /api/departments/members`
- **权限**: 所有认证用户

### 获取科室管理员
- **端点**: `GET /api/departments/admins`
- **权限**: 管理员以上

### 获取科室配置
- **端点**: `GET /api/departments/configs`
- **权限**: 超级管理员

## 患者管理API

### 获取患者列表
- **端点**: `GET /api/patients`
- **权限**: 超级管理员
- **查询参数**: 
  - `deptId`: 科室ID (可选)
  - `page`: 页码
  - `pageSize`: 每页数量

### 导出患者数据
- **端点**: `GET /api/patients/export`
- **权限**: 管理员以上

### 患者注册
- **端点**: `POST /api/patient/register`
- **参数**:
  ```json
  {
    "name": "患者姓名",
    "sex": "性别",
    "age": 年龄,
    "phone": "电话号码",
    "disease": "疾病",
    "groupId": "科室ID"
  }
  ```

## 队列管理API

### 获取队列状态
- **端点**: `GET /api/queue/status`
- **权限**: 所有认证用户

### 获取队列列表
- **端点**: `GET /api/queue/list`
- **权限**: 所有认证用户

### 管理队列列表
- **端点**: `GET /api/admin/queue/list`
- **权限**: 管理员以上

### 队列统计
- **端点**: `GET /api/admin/queue/stats`
- **权限**: 管理员以上

### 所有管理队列
- **端点**: `GET /api/admin/queue/list-all`
- **权限**: 超级管理员

## 咨询系统API

### 获取咨询列表
- **端点**: `GET /api/inquiries`
- **权限**: 管理员以上

### 获取患者咨询
- **端点**: `GET /api/patient/inquiries`
- **权限**: 患者用户

### 回复咨询
- **端点**: `POST /api/inquiries/reply`
- **权限**: 管理员以上
- **参数**:
  ```json
  {
    "inquiryId": "咨询ID",
    "text": "回复内容"
  }
  ```

## 任务管理API

### 获取任务列表
- **端点**: `GET /api/tasks`
- **权限**: 所有认证用户

### 获取任务详情
- **端点**: `GET /api/tasks/{id}`
- **权限**: 所有认证用户

## 消息系统API

### 获取消息列表
- **端点**: `GET /api/messages`
- **权限**: 管理员以上

### 获取患者消息
- **端点**: `GET /api/patient/messages`
- **权限**: 患者用户

## KPI统计API

### 获取所有KPI
- **端点**: `GET /api/kpi/all`
- **权限**: 超级管理员

### 获取个人KPI
- **端点**: `GET /api/kpi/my`
- **权限**: 所有认证用户

### 获取科室KPI
- **端点**: `GET /api/kpi/department`
- **权限**: 管理员以上

## 仪表板API

### 管理仪表板
- **端点**: `GET /api/admin/dashboard`
- **权限**: 管理员以上

## 广告管理API

### 获取广告列表
- **端点**: `GET /api/ads`
- **权限**: 所有认证用户

## 分组管理API

### 获取分组列表
- **端点**: `GET /api/groups`
- **权限**: 所有认证用户

### 创建分组
- **端点**: `POST /api/groups/create`
- **权限**: 超级管理员
- **参数**:
  ```json
  {
    "name": "分组名称",
    "description": "分组描述"
  }
  ```

### 获取邀请列表
- **端点**: `GET /api/groups/invites`
- **权限**: 管理员以上

### 获取转移请求
- **端点**: `GET /api/groups/transfer-requests`
- **权限**: 管理员以上

## 用户绑定API

### 绑定科室
- **端点**: `POST /api/user/bind-department`
- **权限**: 所有认证用户
- **参数**:
  ```json
  {
    "departmentId": "科室ID"
  }
  ```

### 检查科室绑定
- **端点**: `GET /api/user/check-department-binding`
- **权限**: 所有认证用户

### 获取可用科室
- **端点**: `GET /api/user/available-departments`
- **权限**: 所有认证用户

## 管理员功能API

### 获取管理员资料
- **端点**: `GET /api/admin/profile`
- **权限**: 管理员以上

### 获取操作日志
- **端点**: `GET /api/report/log`
- **权限**: 管理员以上

## 健康检查

### 健康检查
- **端点**: `GET /healthz`
- **权限**: 无需认证

## 测试用户账号

系统提供了以下测试用户账号：

| 用户名 | 密码 | 角色 | 权限 |
|--------|------|------|------|
| admin1 | 123456 | admin | 管理员权限 |
| core1 | 123456 | core | 核心用户权限 |
| super | 123456 | super | 超级管理员权限 |
| patient1 | 123456 | patient | 患者权限 |

## 错误处理

所有API返回统一的错误格式：
```json
{
  "ok": false,
  "error": {
    "code": "错误代码",
    "message": "错误信息"
  }
}
```

常见错误代码：
- `api_error`: 通用API错误
- `permission_denied`: 权限不足
- `not_found`: 资源未找到
- `validation_error`: 参数验证错误

## 响应时间

API平均响应时间在0.01-0.21秒之间，性能良好。

## 使用示例

### 登录示例
```javascript
const login = async () => {
  const response = await fetch('http://127.0.0.1:8000/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      username: 'admin1',
      password: '123456'
    })
  });
  const data = await response.json();
  const token = data.token;
  // 保存token用于后续请求
  localStorage.setItem('token', token);
};
```

### 带认证的请求示例
```javascript
const getPatients = async () => {
  const token = localStorage.getItem('token');
  const response = await fetch('http://127.0.0.1:8000/api/patients', {
    method: 'GET',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    }
  });
  const data = await response.json();
  return data;
};
```

这个文档涵盖了所有可用的API端点，包括端点URL、HTTP方法、所需参数、权限要求和响应格式。前端开发人员可以根据这个文档进行开发。
