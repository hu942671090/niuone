#!/usr/bin/env python3
"""market_flow_dashboard_api.py — 大盘资金流向（已废弃）

stock_market_fund_flow() 被 Eastmoney 封禁（ProxyError），无法获取真实数据。
返回 null 值让前端自动隐藏该模块。
"""
import json

def fetch_market_flow():
    return {"total_inflow_yi": None, "total_outflow_yi": None, "net_flow_yi": None}

if __name__ == '__main__':
    print(json.dumps(fetch_market_flow(), ensure_ascii=False))
