# Backend Usage

## Start

```bash
python3 /Users/xin/Documents/micp/backend/server.py
```

服务默认监听 `http://127.0.0.1:9000`，同时会把 `/Users/xin/Documents/micp` 作为静态目录，直接访问即可打开前端页面。

## Cloud Deployment

### Install dependencies

```bash
python3 -m pip install -r /Users/xin/Documents/micp/requirements.txt
```

### Initialize admin account

```bash
python3 /Users/xin/Documents/micp/backend/bootstrap_admin.py
```

默认会创建：

- 用户名：`admin`
- 密码：`Admin@123456`

首次登录后建议立刻修改密码。

### Gunicorn / Flask WSGI

```bash
gunicorn -w 2 -b 0.0.0.0:9000 backend.wsgi:app
```

如果使用阿里云、腾讯云或其他 Linux 云服务器，推荐前面加 Nginx 做反向代理。

## API

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/health`
- `GET /api/schemes`
- `POST /api/schemes`
- `GET /api/dataset`
- `POST /api/dataset`
- `POST /api/train`
- `POST /api/predict`
- `POST /api/analyze`
- `POST /api/report`
- `POST /api/seed`

## Current Notes

- 当前后端已升级为 Flask 架构，便于整体打包发布到云服务器。
- 模型训练与推理采用真实 `scikit-learn` 管线，包括随机森林与 MLPRegressor。
- 数据层支持用户、项目、方案、数据集和模型持久化。
