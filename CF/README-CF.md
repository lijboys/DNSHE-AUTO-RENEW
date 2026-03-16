# DNSHE 免费域名批量自动续期助手 (Cloudflare Worker 版) ☁️

这是一个纯原生 JavaScript 编写的 Cloudflare Worker 脚本，用于全自动批量续期 [DNSHE](https://my.dnshe.com/) 的免费域名。

**为什么推荐 CF Worker 版本？**
相比于 GitHub Actions，CF Worker 最大的优势在于**配置完全可视化**。你可以在 CF 后台的“变量”页面直观地查看、添加或删除你的 DNSHE 账号列表，再也不用对着 GitHub 的隐藏 Secrets 盲人摸象了！

## ✨ 功能特点

- **极简部署**：只需在 CF 网页版粘贴代码即可，零依赖，无需任何服务器。
- **配置透明**：使用 CF 的明文环境变量管理多账号，随时点开随时改，就像记事本一样方便。
- **智能跳过机制**：自动识别“未到续期时间”和“永久有效”的域名，跳过无效请求，减少接口报错。
- **双端消息推送**：支持将详细的分类汇总结果推送到微信（需配合你自己的通知 Worker）和 Telegram。
- **一键手动测试**：在浏览器直接访问 Worker 分配的域名，即可立刻触发执行并查看运行结果。

## 🚀 网页版部署指南

### 1. 创建 Worker 并粘贴代码
1. 登录 Cloudflare 控制台，进入 **Workers & Pages**。
2. 点击 **创建 (Create)** -> **创建 Worker**，随便起个名字（如 `dnshe-renewer`）并部署。
3. 进入该 Worker 的管理页面，点击右上角的 **编辑代码 (Edit code)**。
4. 清空默认代码，把 `worker.js` 中的完整代码粘贴进去，点击 **部署 (Deploy)** 并返回。

### 2. 配置可视化变量 (环境变量)
在当前 Worker 的管理页面，找到左侧菜单的 **设置 (Settings) -> 变量和机密 (Variables and Secrets)**。
在“环境变量”区域点击添加（**注意：类型选择纯文本，不要点击加密图标**）：

| 变量名 | 说明 | 格式示例 | 是否必填 |
| :--- | :--- | :--- | :--- |
| `ACCOUNTS_CONFIG` | 多账号配置，**一行一个账号**，用英文逗号隔开 | `key1,secret1`<br>`key2,secret2` | **必填** |
| `WX_PUSH_URL` | 你的微信推送 Worker 直链（需带密码） | `https://xx.workers.dev/密码` | 选填 |
| `TG_BOT_TOKEN` | Telegram 机器人的 Token | `123456:ABC...` | 选填 |
| `TG_CHAT_ID` | 接收通知的 TG 账号/群组 ID | `123456789` | 选填 |

### 3. 设置 Cron 定时触发器
为了让它每个月自动跑，我们需要加个闹钟：
1. 在 Worker 管理页左侧菜单找到 **触发器 (Triggers)**。
2. 往下拉找到 **Cron 触发器**，点击添加。
3. 选择 **自定义 Cron (Custom Cron)**，输入表达式：`0 2 1 * *` 
   *(代表每个月 1 号的 UTC 时间 2 点，即北京时间上午 10 点执行)*。
4. 保存即可。

### 4. 立即测试
你可以直接在浏览器地址栏输入这个 Worker 的访问链接（类似 `https://dnshe-renewer.你的前缀.workers.dev`）。
页面加载完毕后会直接显示这次跑完的纯文本汇总报告，同时你的微信/TG也会立刻收到推送！
