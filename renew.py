import os
import requests

# ==========================================
# 环境变量配置读取
# ==========================================
# 新增：多账号配置 (格式: key1,secret1 回车换行 key2,secret2)
ACCOUNTS_CONFIG = os.environ.get("ACCOUNTS_CONFIG")

# 兼容保留原有的单账号变量
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

# 推送配置
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
WX_PUSH_URL = os.environ.get("WX_PUSH_URL")

BASE_URL = "https://api005.dnshe.com/index.php?m=domain_hub"

# [上下文] 这里把 header 的生成移到了函数内部，因为不同账号需要不同的密钥
def get_domains(api_key, api_secret):
    """获取指定账号下的所有域名列表"""
    headers = {
        "X-API-Key": api_key,
        "X-API-Secret": api_secret,
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL}&endpoint=subdomains&action=list"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("subdomains", [])

def renew_domain(api_key, api_secret, subdomain_id):
    """发送续期请求"""
    headers = {
        "X-API-Key": api_key,
        "X-API-Secret": api_secret,
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL}&endpoint=subdomains&action=renew"
    payload = {"subdomain_id": subdomain_id}
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_tg_msg(text):
    if not TG_BOT_TOKEN or not TG_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)

def send_wx_msg(text):
    if not WX_PUSH_URL: return
    requests.post(WX_PUSH_URL, json={"title": "🌐 DNSHE 多账号续期通知", "body": text}, timeout=10)

def main():
    # 💡 解析账号配置
    accounts = []
    if ACCOUNTS_CONFIG:
        for line in ACCOUNTS_CONFIG.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'): continue
            parts = line.split(',')
            if len(parts) >= 2:
                accounts.append({"key": parts[0].strip(), "secret": parts[1].strip()})
    
    # 如果没配置多账号，就去读取之前的单账号配置保底
    if not accounts and API_KEY and API_SECRET:
        accounts.append({"key": API_KEY.strip(), "secret": API_SECRET.strip()})

    if not accounts:
        print("❌ 找不到任何账号配置！请在 GitHub Secrets 中设置 ACCOUNTS_CONFIG。")
        return

    print(f"🔍 检测到 {len(accounts)} 个账号，开始执行批量续期...")
    
    total_success, total_skip, total_fail = 0, 0, 0
    summary_lines = [f"<b>🤖 域名批量续期结果 (共{len(accounts)}个账号)</b>\n"]

    # 💡 最外层增加了一个针对账号的循环
    for idx, acc in enumerate(accounts, 1):
        summary_lines.append(f"<b>--- 📦 账号 {idx} ---</b>")
        print(f"\n▶️ 正在处理账号 {idx}...")
        
        try:
            domains = get_domains(acc['key'], acc['secret'])
        except Exception as e:
            msg = f"❌ 获取账号 {idx} 的域名列表失败: {e}"
            print(msg)
            summary_lines.append(msg + "\n")
            continue
        
        if not domains:
            summary_lines.append("⚠️ 该账号下未找到域名\n")
            continue

        # 处理当前账号下的所有域名
        for d in domains:
            full_domain = d.get("full_domain")
            sub_id = d.get("id")
            print(f"⏳ [{full_domain}] 尝试续期...")
            
            try:
                res = renew_domain(acc['key'], acc['secret'], sub_id)
            except Exception as e:
                res = {"success": False, "error": f"请求异常: {str(e)}"}
            
            if res.get("success"):
                total_success += 1
                days = res.get("remaining_days", "未知")
                new_date = str(res.get("new_expires_at", "未知"))[:10]
                line = f"✅ <b>{full_domain}</b>\n└ 剩余: {days}天 | 到期: {new_date}"
                print(f"   -> 成功! 剩余 {days}天")
            else:
                msg = res.get("message") or res.get("error") or "未知报错"
                if "尚未进入" in msg or "时间窗口" in msg:
                    total_skip += 1
                    line = f"⏭️ <b>{full_domain}</b>\n└ 状态: 还没到续期时间"
                    print("   -> 跳过: 还没到续期时间")
                elif "永久" in msg or msg == "未知报错":
                    total_skip += 1
                    reason = "永久域名无需处理" if msg == "未知报错" else msg
                    line = f"♾️ <b>{full_domain}</b>\n└ 状态: {reason}"
                    print(f"   -> 忽略: {reason}")
                else:
                    total_fail += 1
                    line = f"❌ <b>{full_domain}</b>\n└ 失败: {msg}"
                    print(f"   -> 失败: {msg}")
                
            summary_lines.append(line)
        summary_lines.append("") # 账号之间空一行

    # 组装头部统计数据
    summary_lines.insert(1, f"总计成功: {total_success} | 跳过: {total_skip} | 失败: {total_fail}\n")
    final_message = "\n".join(summary_lines)

    send_tg_msg(final_message)
    send_wx_msg(final_message.replace("<b>", "").replace("</b>", ""))

if __name__ == "__main__":
    main()
