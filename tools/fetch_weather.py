# 気象庁の予報JSONと東京の日ごとの気温実績を取ってきて data/jma/ に保存する(GitHub Actions用)
import json, os, sys, csv, datetime, urllib.request
from html.parser import HTMLParser

OUT = "data/jma"
OFFICES = ["130000", "270000", "460100", "230000", "400000", "040000", "016000", "340000"]
HEADERS = {"User-Agent": "Mozilla/5.0 (weather fetch for personal alarm)"}
JST = datetime.timezone(datetime.timedelta(hours=9))


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        return r.read()


class Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr" and ("class", "mtx") in attrs:
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = ""

    def handle_endtag(self, tag):
        if tag == "td" and self.row is not None and self.cell is not None:
            self.row.append(self.cell.strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, d):
        if self.cell is not None:
            self.cell += d


def num(s):
    s = s.replace(")", "").replace("]", "").replace(" ", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def daily(y, m):
    url = ("https://www.data.jma.go.jp/stats/etrn/view/daily_s1.php"
           f"?prec_no=44&block_no=47662&year={y}&month={m}&day=&view=")
    t = Table()
    t.feed(get(url).decode("utf-8", "replace"))
    out = []
    for r in t.rows:
        # 列: 日, 気圧(現地,海面), 降水量(合計,1時間,10分), 気温(平均,最高,最低), ...
        if len(r) < 9 or not r[0].strip().isdigit():
            continue
        mx, mn = num(r[7]), num(r[8])
        if mx is None and mn is None:
            continue
        out.append((f"{y:04d}-{m:02d}-{int(r[0]):02d}", mx, mn))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    ok = True
    for c in OFFICES:
        try:
            data = json.loads(get(f"https://www.jma.go.jp/bosai/forecast/data/forecast/{c}.json"))
            with open(f"{OUT}/forecast-{c}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print("forecast", c, "failed:", e, file=sys.stderr)
            if c == "130000":
                ok = False
    try:
        today = datetime.datetime.now(JST).date()
        prev = today.replace(day=1) - datetime.timedelta(days=1)
        rows = daily(prev.year, prev.month) + daily(today.year, today.month)
        rows = [r for r in rows if r[0] < today.isoformat()][-14:]
        if not rows:
            raise RuntimeError("no rows")
        with open(f"{OUT}/tokyo-daily.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "max", "min"])
            for d, mx, mn in rows:
                w.writerow([d, "" if mx is None else mx, "" if mn is None else mn])
    except Exception as e:
        print("daily failed:", e, file=sys.stderr)
        ok = False
    with open(f"{OUT}/fetched_at.txt", "w") as f:
        f.write(datetime.datetime.now(JST).strftime("%Y-%m-%dT%H:%M") + "\n")
    sys.exit(0 if ok else 1)


main()
