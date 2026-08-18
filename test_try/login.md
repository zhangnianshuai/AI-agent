## 用户注册登录

### 1.用户注册

#### 请求地址

`POST /user/register`

#### 请求参数

1.username: 用户名
2.password: 密码
3.email: 邮箱
4.phone: 手机号

#### 请求示例

```json
{
  "username": "example",
  "password": "password123",
  "email": "example@example.com",
  "phone": "12345678901"
}
```

#### 响应

{
    "code": 200,
    "message": "注册成功",
    "data": {
        "user_id": 1
    }
}

### 2.用户登录

#### 请求地址

`POST /user/login`

#### 请求参数

1.username: 用户名
2.password: 密码

#### 请求示例

```json
{
  "username": "example",
  "password": "password123"
}
```

#### 响应

{
    "code": 200,
    "message": "登录成功",
    "data": {
        user_id: 1
    }
}


