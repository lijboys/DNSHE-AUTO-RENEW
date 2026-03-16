export default {
  // ==========================================
  // [上下文] 浏览器访问触发：方便你随时输入 Worker 网址手动跑一次测试
  // ==========================================
  async fetch(request, env, ctx) {
    const resultText = await runAutoRenew(env);
    return new Response(resultText, {
      headers: { "Content-Type": "text/plain;charset=UTF-8" }
    });
  },

  // ==========================================
  // [上下文] 定时任务触发：配合 CF 后台的 Cron 触发器自动运行
  // ==========================================
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runAutoRenew(env));
  }
};

// 核心执行逻辑
async function runAutoRenew(env) {
  // 💡 读取你在 CF 后台填写的明文变量
  const configStr = env.ACCOUNTS_CONFIG || "";
  const tgToken = env.TG_BOT_TOKEN;
  const tgChatId = env.TG_CHAT_ID;
  const wxPushUrl = env.WX_PUSH_URL;

  const BASE_URL = "https://api005.dnshe.com/index.php?m=domain_hub";

  // 解析账号配置 (按行分割，逗号隔开)
  let accounts = [];
  const lines = configStr.split('\n');
  for (let line of lines) {
    line = line.trim();
    if (!line || line.startsWith('#')) continue;
    const parts = line.split(',');
    if (parts.length >= 2) {
      accounts.push({ key: parts[0].trim(), secret: parts[1].trim() });
    }
  }

  if (accounts.length === 0) {
    return "❌ 找不到任何账号配置！请在 CF 设置 -> 变量 中添加 ACCOUNTS_CONFIG。";
  }

  let totalSuccess = 0, totalSkip = 0, totalFail = 0;
  let summaryLines = [`<b>🤖 域名批量续期结果 (共${accounts.length}个账号)</b>\n`];

  // 遍历每个账号
  for (let idx = 0; idx < accounts.length; idx++) {
    const acc = accounts[idx];
    summaryLines.push(`<b>--- 📦 账号 ${idx + 1} ---</b>`);
    
    try {
      // 获取当前账号的域名列表
      const listReq = await fetch(`${BASE_URL}&endpoint=subdomains&action=list`, {
        headers: { "X-API-Key": acc.key, "X-API-Secret": acc.secret }
      });
      const listRes = await listReq.json();
      const domains = listRes.subdomains || [];

      if (domains.length === 0) {
        summaryLines.push("⚠️ 该账号下未找到域名\n");
        continue;
      }

      // 遍历当前账号下的域名进行续期
      for (let d of domains) {
        const fullDomain = d.full_domain;
        const subId = d.id;
        
        try {
          const renewReq = await fetch(`${BASE_URL}&endpoint=subdomains&action=renew`, {
            method: "POST",
            headers: {
              "X-API-Key": acc.key,
              "X-API-Secret": acc.secret,
              "Content-Type": "application/json"
            },
            body: JSON.stringify({ subdomain_id: subId })
          });
          
          const renewRes = await renewReq.json();
          
          if (renewRes.success) {
            totalSuccess++;
            const days = renewRes.remaining_days || "未知";
            const newDate = (renewRes.new_expires_at || "未知").substring(0, 10);
            summaryLines.push(`✅ <b>${fullDomain}</b>\n└ 剩余: ${days}天 | 到期: ${newDate}`);
          } else {
            const msg = renewRes.message || renewRes.error || "未知报错";
            if (msg.includes("尚未进入") || msg.includes("时间窗口")) {
              totalSkip++;
              summaryLines.push(`⏭️ <b>${fullDomain}</b>\n└ 状态: 还没到续期时间`);
            } else if (msg.includes("永久") || msg === "未知报错") {
              totalSkip++;
              const reason = msg === "未知报错" ? "永久域名无需处理" : msg;
              summaryLines.push(`♾️ <b>${fullDomain}</b>\n└ 状态: ${reason}`);
            } else {
              totalFail++;
              summaryLines.push(`❌ <b>${fullDomain}</b>\n└ 失败: ${msg}`);
            }
          }
        } catch (e) {
          totalFail++;
          summaryLines.push(`❌ <b>${fullDomain}</b>\n└ 续期请求异常: ${e.message}`);
        }
      }
    } catch (e) {
      summaryLines.push(`❌ 获取账号 ${idx + 1} 的域名列表失败: ${e.message}`);
    }
    summaryLines.push(""); // 账号之间空一行
  }

  // 组装最终推送文本
  summaryLines.splice(1, 0, `总计成功: ${totalSuccess} | 跳过: ${totalSkip} | 失败: ${totalFail}\n`);
  const finalMessage = summaryLines.join('\n');

  // 发送 TG 通知
  if (tgToken && tgChatId) {
    await fetch(`https://api.telegram.org/bot${tgToken}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: tgChatId, text: finalMessage, parse_mode: "HTML" })
    }).catch(() => {}); // 忽略推送错误
  }

  // 发送微信通知 (去除 HTML 标签)
  if (wxPushUrl) {
    const wxText = finalMessage.replace(/<b>/g, "").replace(/<\/b>/g, "");
    await fetch(wxPushUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "🌐 DNSHE 多账号续期通知", body: wxText })
    }).catch(() => {}); 
  }

  return finalMessage;
}
