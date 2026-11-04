import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import aiosqlite

APP_NAME = "DIVINE EGG AI TRACKER PRO"
DB_PATH = os.getenv("DATABASE_PATH", "data/divine_egg.db")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DASHBOARD_KEY = os.getenv("DASHBOARD_KEY", "").strip()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(APP_NAME)

Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS spawn_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                map_name TEXT NOT NULL,
                egg_name TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual'
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_spawn_created ON spawn_records(created_at)")
        await db.commit()

async def save_record(map_name: str, egg_name: str, note: str = "", source: str = "manual"):
    created_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO spawn_records(map_name, egg_name, note, created_at, source) VALUES(?,?,?,?,?)",
            (map_name.strip(), egg_name.strip(), note.strip(), created_at, source),
        )
        await db.commit()
        return cur.lastrowid, created_at

async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT COUNT(*) AS total FROM spawn_records")
        total = (await cur.fetchone())["total"]
        cur = await db.execute("""
            SELECT map_name, COUNT(*) AS count
            FROM spawn_records GROUP BY map_name ORDER BY count DESC
        """)
        maps = [dict(x) for x in await cur.fetchall()]
        cur = await db.execute("""
            SELECT egg_name, COUNT(*) AS count
            FROM spawn_records GROUP BY egg_name ORDER BY count DESC LIMIT 10
        """)
        eggs = [dict(x) for x in await cur.fetchall()]
        return {"total_records": total, "by_map": maps, "top_eggs": eggs}

async def get_recent(limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, map_name, egg_name, note, created_at, source "
            "FROM spawn_records ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(x) for x in await cur.fetchall()]

# Telegram commands: /record MAP | EGG | optional note
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🥚 DIVINE EGG AI TRACKER PRO\\n\\n"
        "Commands:\\n"
        "/record MAP | EGG | note - save a spawn record\\n"
        "/stats - show saved statistics\\n"
        "/recent - show latest records\\n"
        "/help - show help\\n\\n"
        "Example:\\n/record Jungle | Divine Egg | found near river"
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)

async def record_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        await update.message.reply_text("Format: /record MAP | EGG | optional note")
        return
    note = parts[2] if len(parts) > 2 else ""
    rid, _ = await save_record(parts[0], parts[1], note, "telegram")
    await update.message.reply_text(f"✅ Saved record #{rid}\\nMap: {parts[0]}\\nEgg: {parts[1]}")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await get_stats()
    lines = [f"📊 Total records: {s['total_records']}"]
    lines.append("\\nBy map:")
    lines.extend([f"• {x['map_name']}: {x['count']}" for x in s["by_map"]] or ["• No data yet"])
    lines.append("\\nTop eggs:")
    lines.extend([f"• {x['egg_name']}: {x['count']}" for x in s["top_eggs"]] or ["• No data yet"])
    await update.message.reply_text("\\n".join(lines))

async def recent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await get_recent(10)
    if not rows:
        await update.message.reply_text("No records yet. Use /record MAP | EGG")
        return
    lines = ["🕘 Latest records:"]
    for r in rows:
        lines.append(f"#{r['id']} | {r['map_name']} | {r['egg_name']}")
    await update.message.reply_text("\\n".join(lines))

telegram_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_app
    await init_db()
    if BOT_TOKEN:
        telegram_app = Application.builder().token(BOT_TOKEN).build()
        telegram_app.add_handler(CommandHandler("start", start_cmd))
        telegram_app.add_handler(CommandHandler("help", help_cmd))
        telegram_app.add_handler(CommandHandler("record", record_cmd))
        telegram_app.add_handler(CommandHandler("stats", stats_cmd))
        telegram_app.add_handler(CommandHandler("recent", recent_cmd))
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        log.info("Telegram bot polling started")
    else:
        log.warning("TELEGRAM_BOT_TOKEN is empty; website/API will run without Telegram bot")
    yield
    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()

app = FastAPI(title=APP_NAME, version="1.0.0", lifespan=lifespan)

class RecordInput(BaseModel):
    map_name: str = Field(min_length=1, max_length=80)
    egg_name: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=500)

def check_admin(key: Optional[str]):
    if not DASHBOARD_KEY:
        raise HTTPException(status_code=503, detail="Set DASHBOARD_KEY in hosting environment first")
    if key != DASHBOARD_KEY:
        raise HTTPException(status_code=401, detail="Invalid dashboard key")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(DASHBOARD_HTML)

@app.get("/health")
async def health():
    return {"status": "ok", "app": APP_NAME, "telegram_configured": bool(BOT_TOKEN)}

@app.get("/api/stats")
async def api_stats():
    return await get_stats()

@app.get("/api/recent")
async def api_recent(limit: int = Query(default=20, ge=1, le=100)):
    return await get_recent(limit)

@app.post("/api/records")
async def api_create_record(payload: RecordInput, x_admin_key: Optional[str] = Header(default=None)):
    check_admin(x_admin_key)
    rid, created = await save_record(payload.map_name, payload.egg_name, payload.note, "dashboard")
    return {"ok": True, "id": rid, "created_at": created}

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Divine Egg AI Tracker PRO</title>
<style>
body{font-family:Arial,sans-serif;background:#101827;color:#eef2ff;margin:0;padding:22px}
main{max-width:980px;margin:auto}h1{color:#facc15}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.card{background:#1e293b;padding:18px;border-radius:14px;margin:12px 0}input,button{padding:12px;border-radius:8px;border:0;margin:5px 0;max-width:100%}
input{background:#e2e8f0}button{background:#eab308;font-weight:bold;cursor:pointer}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px;border-bottom:1px solid #475569}
small{color:#cbd5e1}.muted{color:#cbd5e1}
</style></head><body><main>
<h1>🥚 DIVINE EGG AI TRACKER PRO</h1><p class="muted">Spawn history dashboard · Data is based on records you provide.</p>
<div class="grid"><div class="card"><small>Total records</small><h2 id="total">—</h2></div><div class="card"><small>Maps tracked</small><h2 id="maps">—</h2></div><div class="card"><small>Egg types tracked</small><h2 id="eggs">—</h2></div></div>
<div class="card"><h2>➕ Add spawn record</h2>
<input id="key" type="password" placeholder="Dashboard key"><br>
<input id="map" placeholder="Map name"><br><input id="egg" placeholder="Egg name"><br>
<input id="note" placeholder="Note (optional)" style="width:80%"><br>
<button onclick="addRecord()">Save record</button><span id="status" class="muted"></span></div>
<div class="card"><h2>📊 Most recorded</h2><div id="stats"></div></div>
<div class="card"><h2>🕘 Recent records</h2><div id="recent"></div></div>
<script>
async function load(){
 const s=await (await fetch('/api/stats')).json();
 document.getElementById('total').textContent=s.total_records;
 document.getElementById('maps').textContent=s.by_map.length;
 document.getElementById('eggs').textContent=s.top_eggs.length;
 document.getElementById('stats').innerHTML='<h3>By map</h3>'+table(s.by_map,'map_name')+'<h3>Top eggs</h3>'+table(s.top_eggs,'egg_name');
 const r=await (await fetch('/api/recent?limit=30')).json();
 document.getElementById('recent').innerHTML=table(r,'egg_name',true);
}
function table(rows,name,recent=false){
 if(!rows.length)return '<p class="muted">No data yet.</p>';
 return '<table><tr><th>'+ (recent?'Map':'Name')+'</th><th>Count / Egg</th></tr>'+
 rows.map(x=>'<tr><td>'+esc(recent?x.map_name:x[name])+'</td><td>'+esc(recent?x.egg_name:x.count)+'</td></tr>').join('')+'</table>';
}
function esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function addRecord(){
 const status=document.getElementById('status');status.textContent='Saving...';
 const res=await fetch('/api/records',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Key':document.getElementById('key').value},
 body:JSON.stringify({map_name:document.getElementById('map').value,egg_name:document.getElementById('egg').value,note:document.getElementById('note').value})});
 const data=await res.json();status.textContent=res.ok?'Saved!':(data.detail||'Error');
 if(res.ok){document.getElementById('map').value='';document.getElementById('egg').value='';document.getElementById('note').value='';load();}
}
load();setInterval(load,30000);
</script></main></body></html>"""
