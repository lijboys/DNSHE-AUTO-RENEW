import os
import requests

# ==========================================
# 环境变量配置读取
# ==========================================
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

# Telegram 通知配置
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

# 微信通知配置 (直接使用完整的直链，包含密码)
WX_PUSH_URL = os.environ.get("WX_PUSH_URL")

HEADERS = {
    "X-API-Key": API_KEY,
    "X-API-Secret": API_SECRET,
    "Content-Type": "application/json"
}
BASE_URL = "https://api005.dnshe.com/index.php?m=domain_hub"

def get_domains():
    """获取账号下的所有域名列表"""
    url = f"{BASE_URL}&endpoint=subdomains&action=list"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json().get("subdomains", [])

def renew_domain(subdomain_id):
    """根据 ID 发送续期请求"""
    url = f"{BASE_URL}&endpoint=subdomains&action=renew"
    payload = {"subdomain_id": subdomain_id}
    response = requests.post(url, headers=HEADERS, json=payload)
    return response.json()

def send_tg_msg(text):
    """发送 Telegram 通知"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"TG通知发送失败: {e}")

def send_wx_msg(text):
    """发送微信通知"""
    if not WX_PUSH_URL:
        return
    
    payload = {
        "title": "🌐 DNSHE 批量续期通知",
        "body": text
    }
    try:
        requests.post(WX_PUSH_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"微信通知发送失败: {e}")

def main():
    if not API_KEY or not API_SECRET:
        print("❌ 找不到 API_KEY 或 API_SECRET，脚本终止。请检查 GitHub Secrets 配置。")
        return

    print("🔍 正在获取域名列表并执行批量续期...")
    try:
        domains = get_domains()
    except Exception as e:
        print(f"❌ 获取域名列表失败: {e}")
        return
    
    if not domains:
        msg = "⚠️ 未找到任何域名，请确认账号下是否有已注册的子域名。"
        print(msg)
        send_wx_msg(msg)
        send_tg_msg(msg)
        return

    success_count = 0
    fail_count = 0
    summary_lines = ["<b>🤖 域名批量续期结果</b>\n"]

    # 开始遍历每个域名进行续期
    for d in domains:
        full_domain = d.get("full_domain")
        sub_id = d.get("id")
        
        print(f"⏳ 正在尝试续期域名: {full_domain}...")
        res = renew_domain(sub_id)
        
        if res.get("success"):
            success_count += 1
            days = res.get("remaining_days")
            new_date = res.get("new_expires_at")
            line = f"✅ <b>{full_domain}</b>\n└ 剩余: {days}天 | 到期: {new_date[:10]}"
            print(f"   -> 成功! 剩余 {days}天")
        else:
            fail_count += 1
            msg = res.get("message", "未知错误")
            line = f"❌ <b>{full_domain}</b>\n└ 失败原因: {msg}"
            print(f"   -> 失败: {msg}")
            
        summary_lines.append(line)

    # 组装最终的推送文本
    summary_lines.insert(1, f"总计: {len(domains)} 个 | 成功: {success_count} 个 | 失败: {fail_count} 个\n")
    final_message = "\n".join(summary_lines)

    # 触发双端推送 (微信端去除 HTML 粗体标签以防显示异常)
    send_tg_msg(final_message)
    send_wx_msg(final_message.replace("<b>", "").replace("</b>", ""))

if __name__ == "__main__":
    main()
