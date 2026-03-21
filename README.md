# Chip ATE Analysis System

ATE（自动测试设备）数据分析平台，支持 STS8200/STS8300/ETS364 等多种测试机台数据的上传、解析和可视化分析。

## 功能模块

- **数据上传**：支持 CSV/ZIP 格式，自动识别机台类型
- **参数分析**：直方图、Scatter图、Wafer Map、CPK统计
- **BIN分析**：Bin Map、良率分布图、复测Bin转移分析
- **产品管理**：程序名自动匹配产品名

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + ECharts + AG Grid |
| 后端 | Python + FastAPI + SQLAlchemy |
| 数据库 | PostgreSQL + pgvector |
| 数据处理 | pandas + numpy + scipy |
| 部署 | Nginx + Docker Compose |

## 快速开始

### 后端
\`\`\`bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
\`\`\`

### 前端
\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

## 项目结构


## 系统模块功能介绍

### 后端结构
```
backend/
├── app/
│   ├── main.py              # FastAPI入口，注册所有路由
│   ├── core/
│   │   ├── config.py        # 环境变量配置（数据库URL、密钥等）
│   │   ├── database.py      # SQLAlchemy数据库连接和Session管理
│   │   └── security.py      # JWT token生成/验证、密码哈希
│   ├── models/              # 数据库表结构定义
│   │   ├── user.py          # 用户表（登录信息、存储配置、报表设置）
│   │   ├── lot.py           # LOT表（文件信息、良率、状态、存储路径）
│   │   ├── test_item.py     # 参数统计表（每参数的CPK/均值/良率等）
│   │   ├── bin_summary.py   # Bin汇总表（各Bin数量占比，按Site和DataRange分）
│   │   └── product_mapping.py # 程序名前缀→产品名映射表
│   ├── schemas/             # API输入输出数据结构定义
│   │   ├── user.py          # 用户注册/登录/响应结构
│   │   └── lot.py           # LOT列表响应结构
│   ├── api/routes/          # API接口
│   │   ├── auth.py          # 登录/注册/获取当前用户
│   │   ├── lots.py          # 文件上传/列表/删除，解析入口
│   │   ├── analysis.py      # 参数详情/Bin分析/Wafer Map/复测分析
│   │   └── products.py      # 产品名映射的增删查
│   └── services/
│       ├── stats.py         # 统计计算核心（CPK/均值/标准差/Bin汇总）
│       └── parsers/         # 数据解析模块
│           ├── __init__.py  # 统一入口，自动识别格式调用对应解析器
│           ├── base.py      # ParsedData数据类，统一输出格式
│           ├── detector.py  # 识别ATE机台类型和测试阶段
│           └── acco_parser.py # STS8200/STS8300/多格式解析器
├── migrations/              # Alembic数据库迁移文件
└── .env                     # 环境变量（不上传GitHub）
```

### 前端结构
```
frontend/
├── src/
│   ├── main.ts              # 应用入口，注册插件（Pinia/Router/AgGrid）
│   ├── App.vue              # 根组件，只包含RouterView
│   ├── api/
│   │   └── index.ts         # Axios封装，自动带token，401自动跳登录
│   ├── stores/
│   │   └── auth.ts          # Pinia状态：用户信息、登录/登出操作
│   ├── router/
│   │   └── index.ts         # 路由配置，未登录自动跳/login
│   ├── layouts/
│   │   └── MainLayout.vue   # 主布局：侧边栏+顶部栏+AI悬浮框
│   ├── views/
│   │   ├── LoginView.vue    # 登录/注册页
│   │   ├── HomeView.vue     # 主页：LOT列表、上传、产品名设置
│   │   ├── AnalysisView.vue # 参数详情页：Top Fail图表+参数统计表格
│   │   ├── ParamView.vue    # 单参数分布页：直方图+Scatter+Wafer Map
│   │   └── BinView.vue      # BIN分析页：Bin Map+复测分析+Yield Plot
│   └── assets/
│       └── main.css         # 全局样式（html/body/app撑满全屏）
└── vite.config.ts           # Vite配置，代理/api到后端8000端口
```

### 数据流向
```
用户上传ZIP/CSV
  → lots.py 保存文件
  → detector.py 识别机台类型
  → acco_parser.py 解析表头+数据
  → ParsedData 统一格式
  → stats.py 计算统计量
  → 写入 PostgreSQL（lots/test_items/bin_summary）
  → 原始数据保存为 Parquet 文件

用户查看分析
  → analysis.py 从数据库读统计数据（快）
  → 需要原始分布时从 Parquet 读取计算（按需）
  → 前端 ECharts 渲染图表
  → Canvas 自绘 Wafer Map

见文档 [ARCHITECTURE.md](./ARCHITECTURE.md)
