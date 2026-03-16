# DNSHE 免费域名自动续期助手 🌐

这是一个基于 GitHub Actions 的轻量级自动化脚本，专门用于批量自动续期 [DNSHE](https://my.dnshe.com/) 的免费域名。配置好后，脚本会**每个月 1 号**自动运行一次，遍历你账号下的所有域名进行续期，并将结果推送到你的 Telegram 或微信上。

## ✨ 功能特点

- **全自动运行**：利用 GitHub Actions 定时任务，每月 1 号准时触发，无需服务器。
- **批量续期**：自动获取账号下的所有子域名并逐个执行续期操作。
- **多渠道通知**：
  - **Telegram**：通过 TG Bot 发送详细的续期成功/失败报表。
  - **微信通知**：支持通过你自己部署的 CF (Cloudflare) 网页版 Worker 接收 JSON POST 请求，将汇总信息推送到微信。

## 🚀 使用指南

### 1. 准备工作

在使用之前，你需要准备好以下信息：
- **DNSHE API 密钥**：登录 DNSHE 后台，在“Free Domain”页面底部的 API 管理中生成 `API_KEY` 和 `API_SECRET`。
- **Telegram 机器人**（可选）：在 TG 申请一个 Bot Token，并获取你自己的 Chat ID。
- **微信推送 Worker**（可选）：你在 CF 网页版部署的推送 Worker 链接，包含你的专属鉴权密码（例如：`https://你的worker域名.workers.dev/你的超复杂密码`）。

### 2. 配置 GitHub Secrets

Fork 或将本项目上传到你自己的 GitHub 仓库后，进入仓库的 **Settings -> Secrets and variables -> Actions**，点击 **New repository secret**，添加以下环境变量：

| 变量名 | 说明 | 是否必填 |
| :--- | :--- | :--- |
| `API_KEY` | DNSHE 的 API Key（以 `cfsd_` 开头） | **必填** |
| `API_SECRET` | DNSHE 的 API Secret（仅创建时显示一次） | **必填** |
| `TG_BOT_TOKEN` | Telegram 机器人的 Token | 选填 |
| `TG_CHAT_ID` | 接收通知的 TG 账号或群组 ID | 选填 |
| `WX_PUSH_URL` | 你的 CF 网页版通知 Worker 完整直链，需包含密码 | 选填 |

> **提示**：如果不需要某一种通知方式，直接不填对应的 Secret 即可，脚本会自动跳过。

### 3. 测试运行

配置好 Secrets 后，强烈建议手动运行一次来检查配置是否正确：
1. 点击仓库顶部的 **Actions** 选项卡。
2. 在左侧选择 **DNSHE 域名批量自动续期** 工作流。
3. 点击右侧的 **Run workflow** 按钮。
4. 等待十几秒钟，查看运行日志。如果配置无误，你的手机应该就能收到一封包含所有域名最新到期时间的汇总通知了！

## 🛠️ 文件结构说明

- `renew.py`：核心 Python 脚本，负责调用 DNSHE API 和发送推送通知。
- `.github/workflows/renew.yml`：GitHub Actions 的工作流配置文件，定义了执行环境、触发时间和变量传递。

## ⚠️ 注意事项

- 请妥善保管你的 `API_SECRET` 和推送 `URL`，不要将它们直接硬编码在代码中。
- DNSHE 的 API 请求限制默认为 60 次/分钟，本脚本的批量运行方式在正常域名数量下不会触发限制。
