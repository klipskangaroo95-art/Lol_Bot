"""
v1.0 LOL - EARLY TOP10 + LCS/PRO - DIVERSIFIED - SAME FILTERS AS VAL v4.3
- Game: League of Legends (21779)
- Your faves prioritized: imaqtpie, T1/Faker, thebausffs, tfblade
- EN strict unless 8000v+ mega viral
- No download link, just Twitch link
- Every 4h, no dupes, diversified
"""

import requests, os, json
from datetime import datetime, timedelta, timezone
from collections import Counter

GAME_ID = "21779"  # League of Legends
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
# Use LOL-specific bot if you have one, else fallback to VAL bot
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_LOL") or os.getenv("TELEGRAM_BOT_TOKEN_VAL") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_LOL") or os.getenv("TELEGRAM_CHAT_ID_VAL") or os.getenv("TELEGRAM_CHAT_ID")

SENT_FILE = "sent_ids_lol.txt"
PENDING_FILE = "pending_clips_lol.json"

# Your Top 10 prioritized (Tier 0 early 3-800v <12h)
TOP10 = ["imaqtpie", "thebausffs", "tfblade", "t1", "faker", "tyler1", "caedrel", "doublelift", "sneaky", "bjergsen"]

# LCS + LEC/LCK + pros - Tier 1
PRO_GOAT = [
    # Your faves
    "imaqtpie","thebausffs","tfblade","t1","faker","tyler1","caedrel",
    # Big LoL streamers
    "doublelift","sneaky","bjergsen","loltyler1","xqc","shroud",
    # LCS orgs / official
    "lcs","lec","lck","riotgames","teamliquid","cloud9","100thieves","flyquest","teamliquidlol","c9",
    # LCS/LEC pros
    "jensen","corejj","berserker","apa","yel","impact","spica","jojopyun","inspired","hanssama","caps","rekkles","yagao"
]

BLOCK = ["rule 34", "onlyfans"]

def get_token():
    r=requests.post("https://id.twitch.tv/oauth2/token", params={"client_id":CLIENT_ID,"client_secret":CLIENT_SECRET,"grant_type":"client_credentials"})
    r.raise_for_status()
    return r.json()["access_token"]

def get_clips(token):
    headers={"Client-ID":CLIENT_ID,"Authorization":f"Bearer {token}"}
    started_at=(datetime.now(timezone.utc)-timedelta(hours=36)).isoformat().replace("+00:00","Z")
    params={"game_id":GAME_ID,"first":100,"started_at":started_at}
    all_c=[]
    for _ in range(5):
        resp=requests.get("https://api.twitch.tv/helix/clips", headers=headers, params=params)
        if resp.status_code!=200: break
        data=resp.json()
        all_c.extend(data.get("data",[]))
        cur=data.get("pagination",{}).get("cursor")
        if not cur: break
        params["cursor"]=cur
    return list({c["id"]:c for c in all_c}.values())

def load_sent():
    if not os.path.exists(SENT_FILE): return set()
    with open(SENT_FILE) as f: return set(l.strip() for l in f if l.strip())
def save_sent(s):
    with open(SENT_FILE,"w") as f: f.write("\n".join(sorted(s)))
def load_pending():
    if not os.path.exists(PENDING_FILE): return []
    try:
        with open(PENDING_FILE) as f: return json.load(f)
    except: return []
def save_pending(p):
    with open(PENDING_FILE,"w") as f: json.dump(p,f,indent=2)

def is_english(c):
    lang=(c.get("language") or "en").lower()
    return True if lang in ("en","","other") else False

def tier(e):
    bc=e["broadcaster"].lower()
    vc=e["view_count"]
    try:
        dt=datetime.fromisoformat(e["created_at"].replace("Z","+00:00"))
        age=(datetime.now(timezone.utc)-dt).total_seconds()/3600
    except: age=99
    if bc in TOP10 and 3 <= vc <= 800 and age <= 12:
        return (0, age, -vc)
    if bc in PRO_GOAT or vc>=300 or (vc>=150 and age<=6):
        return (1, 0 if bc in TOP10 else 1, age, -vc)
    return (2, age, -vc)

def main():
    print("=== v1.0 LOL EARLY TOP10 + LCS ===")
    token=get_token()
    clips=get_clips(token)
    print(f"Found {len(clips)} unique last 36h")
    filt=[]
    for c in clips:
        vc=c.get("view_count",0)
        if vc<3: continue
        eng=is_english(c)
        if eng and vc>25000: continue
        if not eng and vc<8000: continue
        if vc>100000: continue
        t=c.get("title","").lower()
        if any(b in t for b in BLOCK): continue
        filt.append(c)
    print(f"After minimal filter (EN<25k or foreign 8000v+ mega): {len(filt)}")

    sent=load_sent()
    pending=load_pending()
    pending=list({p["id"]:p for p in pending}.values())
    pids=set(p["id"] for p in pending)

    added=0
    for c in filt:
        if c["id"] in sent or c["id"] in pids: continue
        try:
            dt=datetime.fromisoformat(c["created_at"].replace("Z","+00:00"))
            ago=f"{(datetime.now(timezone.utc)-dt).total_seconds()/3600:.1f}h ago"
        except: ago=""
        pending.append({
            "id":c["id"],"title":c["title"],"broadcaster":c.get("broadcaster_name",""),
            "broadcaster_login":c.get("broadcaster_name","").lower(),
            "view_count":c["view_count"],"url":c["url"],
            "language":c.get("language","en"),"ago":ago,"created_at":c["created_at"]
        })
        added+=1

    pending=sorted(pending, key=tier)
    pending=[p for p in pending if p["id"] not in sent]
    save_pending(pending)
    print(f"Added {added}, pending {len(pending)}")
    for p in pending[:8]:
        print(f"  T{tier(p)[0]} {p['broadcaster']} {p['view_count']}v {p['ago']} | {p['title'][:35]}")

    if not pending:
        print("All caught up")
        save_sent(sent)
        return

    to_send=[]
    seen_ids=set()
    bc_count=Counter()
    for p in pending:
        if p["id"] in seen_ids or p["id"] in sent: continue
        bc=p["broadcaster_login"]
        if bc_count[bc]>=1: continue
        to_send.append(p)
        seen_ids.add(p["id"])
        bc_count[bc]+=1
        if len(to_send)>=3: break
    if len(to_send)<3:
        for p in pending:
            if p["id"] in seen_ids or p["id"] in sent: continue
            to_send.append(p)
            seen_ids.add(p["id"])
            if len(to_send)>=3: break

    cnt=0
    for e in to_send:
        t=tier(e)[0]
        header="🔥 TOP10 EARLY" if t==0 else "⭐ LCS/PRO" if e["broadcaster_login"] in PRO_GOAT else "📈 TRACTION"
        text=f"{header} 🎮 LEAGUE | {e['view_count']}v | {e['broadcaster']} | {e['ago']}\n{e['title']}\n\n{e['url']}"
        url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r=requests.post(url, json={"chat_id":CHAT_ID,"text":text,"disable_web_page_preview":False})
        print(f"TG send {e['broadcaster']} {r.status_code}")
        if r.status_code==200:
            sent.add(e["id"])
            cnt+=1

    pending=[p for p in pending if p["id"] not in sent]
    save_pending(pending)
    save_sent(sent)
    print(f"DONE v1.0 LOL - sent {cnt}, pending left {len(pending)}")

if __name__=="__main__":
    main()
  
