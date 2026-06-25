#!/usr/bin/env python3
"""牛牛自优化引擎 — 风控暂停时自动回测参数扫描。

用法：
  from self_optimizer import run_optimization, get_last_result
  result = run_optimization()  # 启动后台扫描
"""
import json, os, statistics, threading, time, urllib.request
from pathlib import Path
from typing import Any

from niuone_paths import get_dashboard_home

UA = "Mozilla/5.0"
KLINE_URL = "https://ifzq.gtimg.cn/appstock/app/fqkline/get"
DASHBOARD_HOME = get_dashboard_home(Path(__file__).resolve().parents[1])
STATE_FILE = Path(
    os.environ.get(
        "DASHBOARD_PORTFOLIO_STATE",
        DASHBOARD_HOME / "cron" / "output" / "niuniu_practice_portfolio.json",
    )
).expanduser()
COOLDOWN = 3600  # 1小时最小间隔

POOL = [
    ("600519","茅台"),("600036","招行"),("000333","美的"),("603019","中科曙光"),
    ("600030","中信"),("600900","长电"),("601166","兴业"),("601899","紫金"),
    ("600276","恒瑞"),("601318","平安"),("000858","五粮液"),("002475","立讯"),
    ("600585","海螺"),("600031","三一"),("601088","神华"),("600887","伊利"),
    ("601398","工行"),("000063","中兴"),("600048","保利"),("002230","讯飞"),
]

_opt_state = {"running": False, "result": None, "progress": "", "started_at": ""}


def now_ts(): return time.strftime("%Y-%m-%d %H:%M:%S")


def load_state():
    if not STATE_FILE.exists(): return {}
    return json.loads(STATE_FILE.read_text())


def save_state(st):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".opt.tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=2))
    tmp.replace(STATE_FILE)


def run_optimization(force: bool = False) -> dict[str, Any] | None:
    """启动后台参数扫描。force=True跳过冷却检查。"""
    global _opt_state
    if _opt_state["running"]:
        return dict(_opt_state)
    
    st = load_state()
    if not force and time.time() - st.get("last_self_optimization_ts", 0) < COOLDOWN:
        return None
    
    _opt_state = {"running": True, "started_at": now_ts(), "result": None, "progress": "初始化…"}
    
    def _work():
        global _opt_state
        try:
            # 拉K线
            _opt_state["progress"] = "拉取K线…"
            all_k = {}
            for code, _ in POOL:
                prefix = "sh" if code.startswith(("6","9")) else "sz"
                try:
                    url = f"{KLINE_URL}?param={prefix}{code},day,,,90,qfq"
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        d = json.loads(r.read().decode("utf-8","ignore"))
                    kd = d.get("data",{}).get(f"{prefix}{code}",{}).get("day",[]) or \
                         d.get("data",{}).get(f"{prefix}{code}",{}).get("qfqday",[])
                    rows = [{"c":float(x[2]),"h":float(x[3]),"l":float(x[4])} for x in kd if len(x)>=6]
                    if len(rows)>=60: all_k[code]=rows
                except: pass
            
            _opt_state["progress"] = f"扫描{len(all_k)}只…"
            
            stops=[-3,-4,-5,-6,-7]; scores=[7,8]; holds=[15,20,25]
            best={"sharpe":-999}; total=30; done=0
            
            for sl in stops:
                for ms in scores:
                    for mh in holds:
                        done+=1; wins=0; cnt=0; rets=[]
                        for _,rows in all_k.items():
                            for i in range(30,len(rows)-mh):
                                c=rows[i]["c"]
                                ma20=statistics.mean(rows[j]["c"] for j in range(max(0,i-20),i+1))
                                if c<ma20 or abs((c/ma20-1)*100)>8: continue
                                fi=min(i+mh,len(rows)-1)
                                fr=(rows[fi]["c"]/c-1)*100
                                for j in range(1,fi-i+1):
                                    r=(rows[i+j]["c"]/c-1)*100
                                    if r<=sl or r>=12: fr=r; break
                                rets.append(fr)
                                if fr>0: wins+=1
                                cnt+=1
                        if cnt<10: continue
                        wr=wins/cnt*100; ar=statistics.mean(rets)
                        sr=statistics.stdev(rets) if len(rets)>1 else 1
                        sh=(ar/sr*(252**0.5)) if sr>0 else 0
                        if sh>best["sharpe"]:
                            best={"sharpe":round(sh,3),
                                  "params":{"stop_loss":sl,"min_score":ms,"max_hold":mh},
                                  "results":{"trades":cnt,"win_rate":round(wr,1),"avg_return":round(ar,2)}}
                        _opt_state["progress"]=f"扫描{done}/{total}…"
            
            _opt_state["running"]=False
            _opt_state["result"]=best
            _opt_state["progress"]=(
                f"最优参数：止损{best['params']['stop_loss']}% "
                f"门槛score≥{best['params']['min_score']} "
                f"持仓{best['params']['max_hold']}d "
                f"→ 夏普{best['sharpe']} 胜率{best['results']['win_rate']}%"
            )
            
            st=load_state()
            st["last_self_optimization_ts"]=time.time()
            st["last_optimization_result"]=best
            st["last_optimization_progress"]=_opt_state["progress"]
            save_state(st)
        except Exception as e:
            _opt_state["running"]=False
            _opt_state["progress"]=f"失败:{e}"
    
    threading.Thread(target=_work, daemon=True).start()
    st["last_self_optimization_ts"]=time.time()
    save_state(st)
    return dict(_opt_state)


def get_status() -> dict[str, Any]:
    """获取当前优化状态 + 上次结果。"""
    st = load_state()
    return {
        "running": _opt_state["running"],
        "progress": _opt_state["progress"],
        "started_at": _opt_state["started_at"],
        "last_result": st.get("last_optimization_result"),
        "last_progress": st.get("last_optimization_progress", ""),
    }


def apply_optimization() -> dict[str, Any]:
    """应用上次优化结果到当前策略参数。"""
    st = load_state()
    result = st.get("last_optimization_result")
    if not result:
        return {"applied": False, "error": "无优化结果"}
    
    params = result["params"]
    applied = {}
    
    # 更新交易器的全局参数（通过修改模块常量）
    import niuniu_practice_trader as t
    old_stop = t.STOP_LOSS_PCT
    old_hold = t.MAX_HOLD_DAYS
    
    t.STOP_LOSS_PCT = float(params["stop_loss"])
    t.MAX_HOLD_DAYS = int(params["max_hold"])
    
    applied = {
        "stop_loss": {"old": old_stop, "new": params["stop_loss"]},
        "max_hold": {"old": old_hold, "new": params["max_hold"]},
    }
    
    st["last_applied_optimization"] = {"at": now_ts(), "params": params}
    save_state(st)
    
    return {"applied": True, "changes": applied, "note": "已应用，重启dashboard后生效（内存中的模块已更新）"}
