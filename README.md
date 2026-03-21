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

见文档 [ARCHITECTURE.md](./ARCHITECTURE.md)
