"""こねないパン リール分析（直近30日）

使い方: python3 analyze_reels.py <CSV> [出力.md]
CSV は「リール入力テンプレート.csv」の形、または Meta Business Suite のコンテンツ書き出し。
平均視聴時間がミリ秒（ig_reels_avg_watch_time）の列なら自動で秒に直す。
"""
import csv, math, sys, statistics as st
from datetime import date, timedelta

ALIAS = {
    "date": ["投稿日", "公開日時", "timestamp", "Publish time"],
    "title": ["タイトル", "説明", "caption", "Description"],
    "hook": ["冒頭3秒の内容", "hook"],
    "length": ["動画の長さ(秒)", "時間（秒）", "Duration (sec)"],
    "reach": ["リーチ", "reach", "Reach"],
    "views": ["再生数", "ビュー", "views", "Views", "再生回数"],
    "likes": ["いいね", "いいね！", "likes", "Likes"],
    "comments": ["コメント", "comments", "Comments"],
    "shares": ["シェア", "shares", "Shares"],
    "saved": ["保存", "保存数", "saved", "Saves"],
    "watch_s": ["平均視聴時間(秒)", "平均視聴時間"],
    "watch_ms": ["ig_reels_avg_watch_time"],
}
BENCH = {  # 平均 / Good / Excellent（%）
    "エンゲージメント率": (2, 4, 6),
    "保存率": (1, 2, 4),
    "シェア率": (0.5, 1, 2),
    "コメント率": (0.1, 0.3, 0.6),
}


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        g = {}
        for k, names in ALIAS.items():
            g[k] = next((r[n] for n in names if n in r and r[n] != ""), None)
        for k in ["length", "reach", "views", "likes", "comments", "shares", "saved", "watch_s", "watch_ms"]:
            g[k] = num(g[k]) if g[k] is not None else None
        if g["watch_s"] is None and g["watch_ms"] is not None:
            g["watch_s"] = g["watch_ms"] / 1000
        if g["reach"]:
            out.append(g)
    return out


def recent(posts, days=30):
    cut = (date.today() - timedelta(days=days)).isoformat()
    keep = [p for p in posts if not p["date"] or p["date"][:10] >= cut]
    return keep


def score(p):
    reach = p["reach"]
    p["share_pct"] = (p["shares"] or 0) / reach * 100
    p["save_pct"] = (p["saved"] or 0) / reach * 100
    p["comment_pct"] = (p["comments"] or 0) / reach * 100
    p["eng_pct"] = sum((p[k] or 0) for k in ["likes", "comments", "shares", "saved"]) / reach * 100
    p["spread_pct"] = p["share_pct"] + p["save_pct"]
    w = p["watch_s"] or 0
    p["hook_score"] = w * math.sqrt(reach) * (1 + p["share_pct"] / 100 + p["save_pct"] / 200)
    p["hold_pct"] = w / p["length"] * 100 if p["length"] else None


def tag(p, mw, mr, ms):
    W, R, S = (p["watch_s"] or 0) >= mw, p["reach"] >= mr, p["spread_pct"] >= ms
    if W and R and S:
        return "Winner"
    if W and R:
        return "Hook landed"
    if W:
        return "Strong hook, IG didn't push it"
    if S:
        return "Sharable concept, weak delivery"
    if R:
        return "People clicked, content didn't hold"
    return "Underperformed"


def level(v, b):
    return "Excellent" if v >= b[2] else "Good" if v >= b[1] else "平均以上" if v >= b[0] else "平均未満"


def f(v, d=1):
    return "-" if v is None else f"{v:,.{d}f}"


def report(posts):
    for p in posts:
        score(p)
    mw = st.median(p["watch_s"] or 0 for p in posts)
    mr = st.median(p["reach"] for p in posts)
    ms = st.median(p["spread_pct"] for p in posts)
    mv = st.median(p["views"] or 0 for p in posts)
    mc = st.median(p["comment_pct"] for p in posts)
    for p in posts:
        p["tag"] = tag(p, mw, mr, ms)
    L = [f"# リール分析（{len(posts)}本）", "",
         f"中央値: 平均視聴 {f(mw)}秒 / リーチ {f(mr,0)} / 拡散率(シェア+保存) {f(ms,2)}%", "",
         "## 投稿ごとの Hook Score と診断", "",
         "| 順位 | 投稿日 | タイトル | 冒頭3秒 | リーチ | 再生 | 平均視聴(秒) | 視聴維持率 | 保存率 | シェア率 | Hook Score | 診断 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(sorted(posts, key=lambda p: -p["hook_score"]), 1):
        L.append(f"| {i} | {(p['date'] or '')[:10]} | {(p['title'] or '')[:20]} | {(p['hook'] or '-')[:24]} | {f(p['reach'],0)} | {f(p['views'],0)} | {f(p['watch_s'])} | {f(p['hold_pct'])}% | {f(p['save_pct'],2)}% | {f(p['share_pct'],2)}% | {f(p['hook_score'],0)} | {p['tag']} |")
    L += ["", "## 業界ベンチマーク比較（リーチあたり・全リール合計）", "",
          "| 指標 | あなた | 平均 | Good | Excellent | 判定 |", "|---|---|---|---|---|---|"]
    tr = sum(p["reach"] for p in posts)
    tot = {k: sum((p[k] or 0) for p in posts) for k in ["likes", "comments", "shares", "saved"]}
    mine = {"エンゲージメント率": sum(tot.values()) / tr * 100, "保存率": tot["saved"] / tr * 100,
            "シェア率": tot["shares"] / tr * 100, "コメント率": tot["comments"] / tr * 100}
    for k, b in BENCH.items():
        L.append(f"| {k} | {mine[k]:.2f}% | {b[0]}% | {b[1]}% | {b[2]}% | {level(mine[k], b)} |")
    hidden = [p for p in posts if (p["views"] or 0) < mv and p["comment_pct"] > mc]
    L += ["", "## 再生数は低いのにコメントが多い投稿（需要はある候補）", ""]
    L += [f"- {(p['date'] or '')[:10]} {p['title'] or ''}：再生 {f(p['views'],0)}（中央値 {f(mv,0)}）、コメント率 {p['comment_pct']:.2f}%（中央値 {mc:.2f}%）" for p in hidden] or ["- 該当なし"]
    holds = [p["hold_pct"] for p in posts if p["hold_pct"] is not None]
    if holds:
        L += ["", f"## 視聴維持率（平均視聴時間 ÷ 動画の長さ）: 中央値 {st.median(holds):.0f}%",
              "※ 何秒で離脱したかの細かいグラフは API では取れない。アプリのリールのインサイト画面のスクショで補う。"]
    return "\n".join(L)


if __name__ == "__main__":
    posts = recent(load(sys.argv[1]))
    md = report(posts) if posts else "直近30日のリールがありません。"
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(md)
    print(md)
