# Display Card Manager

管理在**雅虎拍卖 / 煤炉（Mercari）**购入、并在**中国出售**的显卡。记录每张卡的采购与
出售信息、5 类图片/视频（显卡外观、PCB、GPU 核心、GPU-Z、mods 测试），按**交易日期
自动换算日元⇄人民币汇率**，并算出每张卡的成本与利润。

前后端分离：前端 Vue3 + Element Plus，后端 Python + FastAPI，数据存 **MySQL**，
图片/视频存自建**图床**（[Image_hosting](../Image_hosting)）。界面风格与
[FreeMarket_Manager](../FreeMarket_Manager) 一致（深色主题，中/日/英三语）。

## 技术栈

| 层 | 选型 |
|----|------|
| 前端 | Vue 3、Element Plus、Pinia、vue-router（hash）、vue-i18n、ECharts、axios |
| 后端 | FastAPI、uvicorn、PyMySQL（原生 SQL，无 ORM）、PyJWT、bcrypt、requests |
| 数据库 | MySQL 8（utf8mb4） |
| 运行环境 | conda 环境 `displayCard`（Python 3.12） |
| 文件存储 | Image_hosting 图床（`/api/v1` Bearer Token） |
| 汇率源 | 欧洲央行（Frankfurter），按交易日期取历史牌价，本地缓存 |

## 目录结构

```
Display_card/
├─ conf.ini              ← 唯一的文件配置：MySQL 连接 + 监听端口（含密码）
├─ start.bat             ← 开发启动：起后端 + 前端 dev server
├─ pyinstaller.bat       ← 打包成单个 exe（前端 dist 打进 exe）
├─ displaycard.spec      ← PyInstaller 规格
├─ backend/
│  ├─ main.py            ← FastAPI 入口
│  └─ src/
│     ├─ conf.py         ← 读 conf.ini（环境变量可覆盖）
│     ├─ db.py           ← MySQL 连接池 + 查询封装
│     ├─ schema.py       ← 建表 / 迁移 / 种子数据
│     ├─ settings_store.py ← 除 MySQL 外的配置全存 app_settings 表
│     ├─ auth.py / security.py ← JWT + bcrypt
│     ├─ cards.py        ← 管理编号、汇率快照、成本利润换算
│     ├─ fx/             ← 汇率：service（缓存→数据源→降级）+ providers（可插拔）
│     ├─ media/          ← 图床客户端 + 连接配置
│     └─ api/            ← 各路由（auth/cards/media/fx/options/dashboard/system）
└─ webside/              ← Vue 前端
   └─ src/{api,components,views,stores,i18n,...}
```

## 首次运行

### 1. 准备 conda 环境（已存在可跳过）

```powershell
conda create -n displayCard python=3.12
conda activate displayCard
pip install -r backend/requirements.txt
```

### 2. 配置 MySQL 连接

编辑项目根目录的 `conf.ini`，`[mysql]` 段至少填对 `host` / `user` / `password`：

```ini
[mysql]
host = 127.0.0.1
port = 3306
user = your_user
password = your_password
database = display_card
charset = utf8mb4

[server]
host = 0.0.0.0
port = 9910
```

库 `display_card` 不存在时，若账号有建库权限会自动创建；否则请先手动建一个空库：

```sql
CREATE DATABASE display_card CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

> 每一项都能用环境变量覆盖（如 `DISPLAYCARD_MYSQL_PASSWORD`），方便打包后在不同机器
> 部署时不改文件。

### 3. 启动

双击 `start.bat`，或分别：

```powershell
# 后端
conda activate displayCard
cd backend
python main.py            # 监听 9910

# 前端（另开一个终端）
cd webside
npm install
npm run dev               # 监听 9911
```

浏览器打开 **http://localhost:9911**。首次登录 `admin` / `admin`，登录后请立即在
「系统配置 → 账号」中改密码。

### 4. 配置图床

到「系统配置 → 图床」填写：

- **后端连接地址**：本程序连图床用，通常内网直连，如 `http://127.0.0.1:9990`
- **公开访问地址**：浏览器打开图片用，留空则同上
- **项目标识**：在图床里为本项目创建的 project slug，如 `displaycard`
- **API Token**：图床项目详情里复制

保存后点「测试连接」验证。

> **图床需支持视频**：本项目要上传 mp4 等视频，请确认图床端已放开视频扩展名并对视频跳过
> PIL 图片校验（图床默认只认 8 种图片格式）。

## 核心业务约定

### 汇率

- 汇率一经取到就**快照写死在卡片行里**（`purchase_fx_rate` / `sale_fx_rate`），之后不再
  重算——已发生交易的盈亏不应随每日汇率波动。
- 周末 / 节假日无牌价时**自动回退**到不晚于该日的最近一个发布日，并记录实际牌价日。
- 需要精确成交价时可在卡片上**手工填汇率**（`fx_manual=1`），此后自动刷新跳过该卡。
- ECB 是参考中间价，不等于实际换汇成交价。

### 金额与币种

每个金额字段自带币种下拉（日元 / 人民币）。折算成人民币时：

| 金额 | 用哪个汇率 |
|------|-----------|
| 购入价、国际运费 | 购入日汇率 |
| 国内运费、出售价 | 出售日汇率 |

**利润 = 出售价 −（购入价 + 国际运费 + 国内运费）**，全部折成人民币。任何一项因缺汇率
折不出来时，含它的合计返回空而非按 0 计——避免算出一个偏高的假利润。

### 状态流转

`已购入 → 待测试 → 测试通过 / 测试不通过 → 回国中 → 转寄中 → 已签收 → 已打款`

「已签收」「已打款」是中国买家的动作；走到「已打款」这笔生意才算完。每次状态变更都记
一条流转日志，可在卡片详情里追溯（例如卡在海关卡了多久）。

## 打包

```powershell
pyinstaller.bat
```

产物在 `Releases\v1.0.0\`，含 `DisplayCardManager.exe`（前端已打进 exe）和一份
`conf.ini` 模板。目标机需：MySQL 可达、Edge/浏览器。改前端文案无需重打包——在 exe 同
目录放一个 `webside\dist` 即可热替换。

## 端口

| 服务 | 端口 |
|------|------|
| 前端 dev server | 9911 |
| 后端 API | 9910 |
| 图床（另一项目） | 9990 |

## 数据表

`users`、`cards`、`card_media`、`card_status_logs`、`gpu_brands`、`gpu_models`、
`app_settings`、`fx_rates`。建表与增量迁移在 `backend/src/schema.py`，启动时自动执行。
