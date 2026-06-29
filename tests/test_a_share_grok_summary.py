#!/usr/bin/env python3
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app"
sys.path.insert(0, str(SRC))
MODULE_PATH = SRC / "a_share_grok_summary.py"


def load_module():
    spec = importlib.util.spec_from_file_location("a_share_grok_summary_under_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AShareGrokSummaryTests(unittest.TestCase):
    def test_parse_accepts_json_fence(self):
        mod = load_module()

        parsed = mod.parse_a_share_grok_content("""```json
{"tone":"cautious","tone_label":"谨慎","summary":"盘面分化，先控仓。","guidance_lines":["风险级别：谨慎","开仓节奏：本轮最多1笔"],"focus_lines":["资金流向"],"risk_lines":["跌停扩散"]}
```""")

        self.assertEqual(parsed["tone"], "cautious")
        self.assertEqual(parsed["tone_label"], "谨慎")
        self.assertEqual(parsed["guidance_lines"][1], "开仓节奏：本轮最多1笔")

    def test_apply_grok_report_puts_model_guidance_first(self):
        mod = load_module()
        original_call = mod.call_grok_api
        original_model = mod.A_SHARE_MODEL_SUMMARY_MODEL
        try:
            mod.A_SHARE_MODEL_SUMMARY_MODEL = "model-test"
            mod.call_grok_api = lambda messages, max_tokens=1800: json.dumps({
                "tone": "defensive",
                "tone_label": "防守",
                "summary": "A股午盘涨少跌多，资金分散，午后先防守。",
                "guidance_lines": [
                    "风险级别：防守",
                    "开仓节奏：午后只观察，除非主线回封确认。",
                    "买入指引：只看资金净流入且回踩不破的方向。",
                    "卖出/风控：弱于板块和放量回落的持仓先处理。",
                ],
                "focus_lines": ["观察跌停数量是否扩散"],
                "risk_lines": ["下跌家数占优时不追高"],
            }, ensure_ascii=False)
            local_report = """牛牛大王，A股午盘总结来了：

📊 **市场概况**
上涨 `1000` · 下跌 `3900`

🎯 **今日买卖指引**
· 风险级别：平衡
· 开仓节奏：午后最多3-4只

🔥 **热门板块**
`通信` +1.20%
"""

            report = mod.apply_grok_to_a_share_report(local_report, title="A股午盘总结")
        finally:
            mod.call_grok_api = original_call
            mod.A_SHARE_MODEL_SUMMARY_MODEL = original_model

        self.assertIn("生成模型 `model-test`", report)
        self.assertIn("A股午盘涨少跌多", report)
        self.assertLess(report.index("风险级别：防守"), report.index("本地规则快照"))
        self.assertNotIn("风险级别：平衡", report)
        self.assertIn("`通信` +1.20%", report)


if __name__ == "__main__":
    unittest.main()
