import os
import requests
import traceback
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from supabase import create_client, Client

app = FastAPI()

# 自動清除變數前後可能不小心複製到的隱形空白
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
BRAWL_API_TOKEN = os.environ.get("BRAWL_API_TOKEN", "").strip()
PLAYER_TAGS_STR = os.environ.get("PLAYER_TAGS", "#你的標籤").strip()
PLAYER_TAGS = [tag.strip() for tag in PLAYER_TAGS_STR.split(",")]

error_detail = ""
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    supabase = None
    error_detail = traceback.format_exc() # 抓取最底層的錯誤原因

def update_brawl_data():
    if not supabase or not BRAWL_API_TOKEN:
        return
        
    headers = {"Authorization": f"Bearer {BRAWL_API_TOKEN}"}
    
    for tag in PLAYER_TAGS:
        tag_formatted = tag.replace("#", "%23")
        url = f"https://bsproxy.royaleapi.dev/v1/players/{tag_formatted}/battlelog"
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            continue
            
        battles = response.json().get("items", [])
        for battle in battles:
            battle_time = battle.get("battleTime")
            try:
                existing = supabase.table("battlelog").select("id").eq("battle_time", battle_time).eq("account", tag).execute()
                if len(existing.data) > 0:
                    continue
            except:
                continue
                
            b = battle.get("battle", {})
            event = battle.get("event", {})
            my_brawler = ""
            brawler_trophies = ""
            
            players_list = []
            if "teams" in b:
                for team in b["teams"]:
                    players_list.extend(team)
            elif "players" in b:
                players_list = b["players"]
                
            for player in players_list:
                if player.get("tag") == tag:
                    my_brawler = player.get("brawler", {}).get("name", "")
                    brawler_trophies = str(player.get("brawler", {}).get("trophies", ""))

            new_record = {
                "account": tag,
                "battle_time": battle_time,
                "mode": event.get("mode", "unknown"),
                "map": event.get("map", "unknown"),
                "type": b.get("type", "unknown"),
                "my_brawler": my_brawler,
                "brawler_trophies": brawler_trophies,
                "result": b.get("result", "draw"),
                "trophy_change": str(b.get("trophyChange", 0))
            }
            try:
                supabase.table("battlelog").insert(new_record).execute()
            except:
                pass

@app.get("/")
def read_root():
    # 如果資料庫連線失敗，印出完整的診斷報告
    if not supabase:
        html = f"""
        <body style='background:black; color:white; font-family:sans-serif; padding:20px;'>
            <h1 style='color:#ff4444;'>⚠️ 連線失敗，啟動除錯報告</h1>
            <p><b>URL 讀取長度:</b> {len(SUPABASE_URL)} (如果為 0，代表 Render 沒傳遞到這個變數)</p>
            <p><b>KEY 讀取長度:</b> {len(SUPABASE_KEY)} (如果為 0，代表 Render 沒傳遞到這個變數)</p>
            <p><b>目前讀取到的 URL:</b> {SUPABASE_URL}</p>
            <h3>⛔ 詳細錯誤日誌：</h3>
            <pre style='color:#ffff00; background:#222; padding:15px; border-radius:5px; overflow-x:auto;'>{error_detail}</pre>
        </body>
        """
        return HTMLResponse(content=html)
        
    try:
        res = supabase.table("battlelog").select("*").order("battle_time", desc=True).limit(20).execute()
        data = res.data
    except Exception as e:
        return HTMLResponse(f"<h1 style='color:white; background:black;'>資料表讀取失敗: {str(e)}<br>請確認 Supabase 裡面是否真的有建立 battlelog 資料表？</h1>")
        
    # 如果成功，顯示正常的主控台介面
    html = """
    <html>
    <head>
        <title>荒野亂鬥戰術主控台</title>
        <style>
            body { background-color: #121212; color: #ffffff; font-family: 'Segoe UI', sans-serif; margin: 40px; }
            h1 { color: #00ff88; text-align: center; }
            .btn { display: block; width: 220px; margin: 20px auto; padding: 12px; text-align: center; background: #00ff88; color: #121212; text-decoration: none; font-weight: bold; border-radius: 8px; font-size: 16px; transition: 0.3s; }
            .btn:hover { background: #00cc6a; transform: scale(1.05); }
            table { width: 100%; border-collapse: collapse; margin-top: 30px; box-shadow: 0 0 20px rgba(0,255,136,0.1); }
            th, td { padding: 15px; text-align: center; border-bottom: 1px solid #333; }
            th { background-color: #1e1e1e; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
            tr:hover { background-color: #1a1a1a; }
            .win { color: #00ff88; font-weight: bold; }
            .defeat { color: #ff4444; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🎮 戰術主控台 (Supabase 雲端版)</h1>
        <a href="/update" class="btn" target="_blank">🔄 讀取最新戰績</a>
        <table>
            <tr><th>帳號</th><th>時間</th><th>模式</th><th>地圖</th><th>使用英雄</th><th>結果</th><th>獎盃變化</th></tr>
    """
    for row in data:
        result_text = row.get('result', '')
        css_class = "win" if result_text == "victory" else ("defeat" if result_text == "defeat" else "")
        html += f"""
            <tr>
                <td>{row.get('account')}</td>
                <td>{row.get('battle_time')}</td>
                <td>{row.get('mode')}</td>
                <td>{row.get('map')}</td>
                <td>{row.get('my_brawler')}</td>
                <td class="{css_class}">{result_text.upper()}</td>
                <td>{row.get('trophy_change')}</td>
            </tr>
        """
    html += "</table></body></html>"
    return HTMLResponse(content=html)

@app.get("/update")
def trigger_update(background_tasks: BackgroundTasks):
    background_tasks.add_task(update_brawl_data)
    return {"message": "✅ 爬蟲已在背景啟動！正在去抓資料並寫入，請關閉此頁面，等 5 秒後重整首頁。"}
