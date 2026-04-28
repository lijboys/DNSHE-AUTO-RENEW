import os
import requests
import time
from datetime import datetime

# ==========================================
# 环境变量配置
# ==========================================
ACCOUNTS_CONFIG = os.environ.get("ACCOUNTS_CONFIG")
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
WX_PUSH_URL = os.environ.get("WX_PUSH_URL")

DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
RETRY_TIMES = 3
BASE_URL = "https://api005.dnshe.com/index.php?m=domain_hub"

# ==========================================
# V2.0 API 客户端
# ==========================================
class DNSHEClient:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.headers = {
            "X-API-Key": api_key,
            "X-API-Secret": api_secret,
            "Content-Type": "application/json"
        }
    
    def _request(self, method: str, endpoint: str, action: str, params=None, json_data=None):
        """带重试和速率限制处理的请求"""
        url = f"{BASE_URL}&endpoint={endpoint}&action={action}"
        
        for attempt in range(RETRY_TIMES):
            try:
                if method.upper() == "GET":
                    resp = requests.get(url, headers=self.headers, params=params, timeout=15)
                else:
                    resp = requests.post(url, headers=self.headers, json=json_data, timeout=15)
                
                # 处理速率限制
                if resp.status_code == 429:
                    reset_time = resp.json().get("details", {}).get("reset_at")
                    wait = 5 if not reset_time else 10
                    print(f"    ⚠️ 触发速率限制，等待 {wait}s...")
                    time.sleep(wait)
                    continue
                
                resp.raise_for_status()
                return resp.json()
                
            except Exception as e:
                if attempt == RETRY_TIMES - 1:
                    raise
                time.sleep(2 ** attempt)  # 指数退避
        return None

    def get_all_domains(self):
        """
        V2.0 分页获取所有域名
        默认每页 200，最大支持 500，这里用 200 平衡性能和请求数
        """
        all_domains = []
        page = 1
        per_page = 200
        
        while True:
            params = {
                "page": page,
                "per_page": per_page,
                "sort_by": "expires_at",  # 按过期时间排序，优先处理即将过期的
                "sort_dir": "asc"
            }
            
            data = self._request("GET", "subdomains", "list", params=params)
            
            if not data or not data.get("success"):
                error_msg = data.get("message", "未知错误") if data else "请求失败"
                raise Exception(f"获取域名列表失败: {error_msg}")
            
            domains = data.get("subdomains", [])
            all_domains.extend(domains)
            
            # 检查是否有更多页
            pagination = data.get("pagination", {})
            if not pagination.get("has_more", False):
                break
            
            page += 1
            
            # 礼貌性延迟，避免触发 60 req/min 限制
            if page % 50 == 0:
                time.sleep(1)
        
        return all_domains

    def renew_domain(self, subdomain_id: str):
        """V2.0 续期接口，返回完整响应"""
        return self._request(
            "POST", 
            "subdomains", 
            "renew", 
            json_data={"subdomain_id": subdomain_id}
        )


# ==========================================
# 通知函数（保持不变）
# ==========================================
def send_tg_msg(text: str):
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram 推送失败: {e}")

def send_wx_msg(text: str):
    if not WX_PUSH_URL:
        return
    try:
        requests.post(WX_PUSH_URL, json={
            "title": "🌐 DNSHE V2.0 续期通知",
            "body": text
        }, timeout=10)
    except Exception as e:
        print(f"微信推送失败: {e}")


# ==========================================
# 主程序
# ==========================================
def main():
    start_time = time.time()
    print(f"🚀 DNSHE V2.0 批量续期任务启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 解析账号配置
    accounts = []
    if ACCOUNTS_CONFIG:
        for line in ACCOUNTS_CONFIG.strip().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                accounts.append({"key": parts[0], "secret": parts[1]})
    
    if not accounts and API_KEY and API_SECRET:
        accounts.append({"key": API_KEY, "secret": API_SECRET})

    if not accounts:
        print("❌ 未找到任何账号配置！")
        return

    print(f"🔍 共 {len(accounts)} 个账号\n")
    
    total_success = total_skip = total_fail = total_domains = 0
    summary_lines = [f"<b>🤖 DNSHE V2.0 续期报告（{len(accounts)} 账号）</b>\n"]

    for idx, acc in enumerate(accounts, 1):
        summary_lines.append(f"<b>📦 账号 {idx}</b>")
        print(f"▶️ 账号 {idx}: ", end="")
        
        client = DNSHEClient(acc['key'], acc['secret'])
        
        try:
            domains = client.get_all_domains()
        except Exception as e:
            msg = f"❌ 获取域名失败: {e}"
            print(msg)
            summary_lines.append(msg + "\n")
            continue
        
        total_domains += len(domains)
        print(f"发现 {len(domains)} 个域名")
        
        if not domains:
            summary_lines.append("⚠️ 无域名\n")
            continue

        acc_success = acc_skip = acc_fail = 0
        
        for d in domains:
            full_domain = d.get("full_domain", "未知")
            sub_id = d.get("id")
            status = d.get("status")  # V2.0 新增：检查域名状态
            
            # 跳过已暂停/过期的（V2.0 特性）
            if status not in ["active", None]:
                print(f"   ⏭️ [{full_domain}] 状态为 {status}，跳过")
                acc_skip += 1
                total_skip += 1
                summary_lines.append(f"⏭️ <b>{full_domain}</b>\n└ 状态: {status}")
                continue
            
            print(f"   ⏳ [{full_domain}]...", end=" ")
            
            if DRY_RUN:
                print("🧪 模拟")
                line = f"🧪 <b>{full_domain}</b>（模拟续期）"
                acc_success += 1
            else:
                try:
                    res = client.renew_domain(sub_id)
                except Exception as e:
                    res = {"success": False, "error_code": "exception", "message": str(e)}
                
                if res.get("success"):
                    acc_success += 1
                    total_success += 1
                    days = res.get("remaining_days", "?")
                    new_date = str(res.get("new_expires_at", "未知"))[:10]
                    charged = res.get("charged_amount", 0)
                    
                    cost_info = f"（扣费 {charged} 积分）" if charged else "（免费）"
                    print(f"✅ 成功 {cost_info}")
                    line = f"✅ <b>{full_domain}</b>\n└ 剩余 {days} 天 | 到期 {new_date} {cost_info}"
                else:
                    error_code = res.get("error_code", "")
                    msg = res.get("message", "未知错误")
                    
                    # V2.0 精确错误码判断
                    if error_code == "renewal_not_yet_available" or "尚未进入" in msg:
                        acc_skip += 1
                        total_skip += 1
                        print(f"⏭️ 未到时间")
                        line = f"⏭️ <b>{full_domain}</b>\n└ 未到续期时间"
                    elif error_code == "subdomain_never_expires" or "永久" in msg:
                        acc_skip += 1
                        total_skip += 1
                        print(f"♾️ 永久域名")
                        line = f"♾️ <b>{full_domain}</b>\n└ 永久域名"
                    elif error_code == "insufficient_balance":
                        acc_fail += 1
                        total_fail += 1
                        print(f"❌ 余额不足")
                        line = f"❌ <b>{full_domain}</b>\n└ 余额不足无法续期"
                    else:
                        acc_fail += 1
                        total_fail += 1
                        print(f"❌ {msg[:30]}")
                        line = f"❌ <b>{full_domain}</b>\n└ 失败: {msg}"
            
            summary_lines.append(line)
        
        summary_lines.append(f"账号 {idx}: 成功 {acc_success} | 跳过 {acc_skip} | 失败 {acc_fail}\n")

    # 最终统计
    duration = round(time.time() - start_time, 2)
    summary_lines.insert(1, f"📊 总域名: {total_domains} | 成功: {total_success} | 跳过: {total_skip} | 失败: {total_fail}\n")
    summary_lines.insert(2, f"⏱️ 耗时: {duration}s\n")

    final_html = "\n".join(summary_lines)
    final_text = final_html.replace("<b>", "**").replace("</b>", "**")

    send_tg_msg(final_html)
    send_wx_msg(final_text)

    print(f"\n✅ 完成！总域名 {total_domains}，耗时 {duration}s")

if __name__ == "__main__":
    main()
