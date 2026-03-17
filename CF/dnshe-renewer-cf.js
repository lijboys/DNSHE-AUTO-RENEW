/**
 * DNSHE 免费域名批量续期助手 (纯净配置版)
 * 变量需求: ACCOUNTS_CONFIG, WX_API_URL, WX_AUTH_KEY, (选填 MY_URL, TG_BOT_TOKEN, TG_CHAT_ID)
 */

export default {
  // ================= 定时任务入口 =================
  async scheduled(event, env, ctx) {
    await runAutoRenew(env, env.MY_URL);
  },

  // ================= 浏览器路由入口 =================
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // 💡 路由 1：专门负责渲染好看的详情页 (只有配置了 MY_URL 才会用到)
    if (url.pathname === '/detail') {
      const title = url.searchParams.get('title') || '续期详情';
      const content = url.searchParams.get('content') || '暂无内容';
      
      const html = `
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
          <title>${title}</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f5f7; color: #333; margin: 0; padding: 20px; line-height: 1.6; }
            .container { max-width: 600px; margin: 0 auto; }
            .card { background: #ffffff; border-radius: 16px; padding: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }
            .header { border-bottom: 1px solid #eee; padding-bottom: 16px; margin-bottom: 16px; }
            h2 { margin: 0; font-size: 20px; color: #173177; font-weight: 600; }
            pre { white-space: pre-wrap; word-wrap: break-word; font-family: inherit; margin: 0; font-size: 15px; color: #444; }
            .footer { margin-top: 24px; text-align: center; font-size: 12px; color: #999; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="card">
              <div class="header">
                <h2>${title}</h2>
              </div>
              <pre>${content}</pre>
            </div>
            <div class="footer">🚀 Powered by Cloudflare Workers</div>
          </div>
        </body>
        </html>
      `;
      return new Response(html, { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } });
    }
    
    // 💡 路由 2：防误触的专属手动执行接口
    if (url.pathname === '/run') {
      const myUrl = env.MY_URL; // 🚫 彻底去掉了自动抓取！只有你在变量里老老实实配了 MY_URL，才会生成网页！
      const resultText = await runAutoRenew(env, myUrl);
      return new Response(`手动触发完成！\n\n${resultText}`, { status: 200, headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }
    
    // 💡 路由 3：默认首页，防止外人乱点
    return new Response("🤖 DNSHE 续期 Worker 运行正常 🟢\n\n手动测试运行请访问: /run", { status: 200, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
};

// ================= 核心业务逻辑 =================
async function runAutoRenew(env, myUrl) {
  const configStr = env.ACCOUNTS_CONFIG || "";
  const wxApiUrl = env.WX_API_URL;
  const wxAuthKey = env.WX_AUTH_KEY;
  const tgToken = env.TG_BOT_TOKEN;
  const tgChatId = env.TG_CHAT_ID;

  const BASE_URL = "https://api005.dnshe.com/index.php?m=domain_hub";

  let accounts = [];
  if (configStr) {
    for (let line of configStr.split('\n')) {
      line = line.trim();
      if (!line || line.startsWith('#')) continue;
      const parts = line.split(',');
      if (parts.length >= 2) accounts.push({ key: parts[0].trim(), secret: parts[1].trim() });
    }
  }

  if (accounts.length === 0) return "❌ 找不到账号配置，请检查变量 ACCOUNTS_CONFIG";

  let totalSuccess = 0, totalSkip = 0, totalFail = 0;
  let reportLines = [];

  for (let idx = 0; idx < accounts.length; idx++) {
    const acc = accounts[idx];
    reportLines.push(`📦 账号 [${idx + 1}]`);
    
    try {
      const listReq = await fetch(`${BASE_URL}&endpoint=subdomains&action=list`, {
        headers: { "X-API-Key": acc.key, "X-API-Secret": acc.secret }
      });
      const listRes = await listReq.json();
      const domains = listRes.subdomains || [];

      if (domains.length === 0) {
        reportLines.push("  ⚠️ 暂无活跃域名\n");
        continue;
      }

      for (let d of domains) {
        const fullDomain = d.full_domain;
        const subId = d.id;
        try {
          const renewReq = await fetch(`${BASE_URL}&endpoint=subdomains&action=renew`, {
            method: "POST",
            headers: { "X-API-Key": acc.key, "X-API-Secret": acc.secret, "Content-Type": "application/json" },
            body: JSON.stringify({ subdomain_id: subId })
          });
          const renewRes = await renewReq.json();
          
          if (renewRes.success) {
            totalSuccess++;
            const days = renewRes.remaining_days || "?";
            const newDate = (renewRes.new_expires_at || "?").substring(0, 10);
            reportLines.push(`✅ ${fullDomain} (剩余:${days}天)`);
          } else {
            const msg = renewRes.message || renewRes.error || "未知报错";
            if (msg.includes("尚未进入") || msg.includes("时间窗口")) {
              totalSkip++;
              reportLines.push(`⏭️ ${fullDomain} (未到时间)`);
            } else if (msg.includes("永久") || msg.includes("never expire") || msg === "未知报错") {
              // 修正了 never expire 的判断逻辑，现在会被正确归类为跳过/永久有效
              totalSkip++;
              reportLines.push(`♾️ ${fullDomain} (永久有效)`);
            } else {
              totalFail++;
              reportLines.push(`❌ ${fullDomain} (失败:${msg})`);
            }
          }
        } catch (e) {
          totalFail++;
          reportLines.push(`❌ ${fullDomain} (请求超时)`);
        }
      }
    } catch (e) {
      reportLines.push(`❌ 账号 ${idx + 1} 列表获取失败`);
    }
    reportLines.push(""); 
  }

  const nowStr = new Date().toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
  const title = `🌐 DNSHE 续期: 成功 ${totalSuccess} 个`;
  const finalMessage = [
    `🕒 执行时间: ${nowStr}`,
    `------------------------------`,
    `📊 成功: ${totalSuccess} | 跳过: ${totalSkip} | 失败: ${totalFail}`,
    `------------------------------`,
    ...reportLines,
    `💡 你的域名正在被安全守护中`
  ].join("\n");

  // ================= 发送 TG 通知 =================
  if (tgToken && tgChatId) {
    // 移除了包裹 finalMessage 的 <pre> 标签，恢复普通文本格式
    const tgMsg = `<b>${title}</b>\n\n${finalMessage}`;
    await fetch(`https://api.telegram.org/bot${tgToken}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: tgChatId, text: tgMsg, parse_mode: "HTML" })
    }).catch(() => {});
  }

  // ================= 发送微信通知 =================
  if (wxApiUrl && wxAuthKey) {
    try {
      // 默认基础负载，不传 URL
      let pushPayload = {
        key: wxAuthKey,
        title: title,
        content: finalMessage
      };

      // 💡 只有当你确实配置了 MY_URL 环境变量时，才会传 url 过去替换掉你的默认跳转
      if (myUrl) {
        const cleanMyUrl = myUrl.replace(/\/$/, '');
        pushPayload.url = `${cleanMyUrl}/detail?title=${encodeURIComponent(title)}&content=${encodeURIComponent(finalMessage)}`;
      }

      await fetch(wxApiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pushPayload)
      });
    } catch (err) {
      console.log("微信发送失败:", err);
    }
  }

  return finalMessage;
}
