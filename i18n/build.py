"""把 src/ 的繁體原稿構建成三語（繁中、简中、English）合一的頁面。

用法：
    python3 i18n/build.py                 # 輸出到倉庫根目錄（含 <!doctype html>）
    python3 i18n/build.py --artifact DIR  # 另外輸出一份不含 doctype 的副本到 DIR（給預覽用）

需要：pip install opencc-python-reimplemented

翻譯來源：
    i18n/en.json      繁中片段 → 英文（用 i18n/extract.py 列出所有片段）
    CN_FIX（本文件）  繁簡轉換後的大陸用語修正
修改內容時只改 src/ 裡的繁體原稿和 en.json，然後重新運行本腳本。
"""
import json, re, sys, pathlib
import opencc
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from extract import segments, strip_comments, HAN

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = ['refinery-flows', 'refinery-compare', 'refinery-shandong']
LANGS = ['zh-TW', 'zh-CN', 'en']
HTML_LANG = {'zh-TW': 'zh-Hant-TW', 'zh-CN': 'zh-Hans-CN', 'en': 'en-US'}

# 繁簡轉換只轉字（t2s），大陸用語在這裡逐個替換；不用 tw2sp，它會把「裝置」改成「设备」等電腦用語
CN_FIX = [
    ('计画', '项目'), ('计划', '项目'), ('产业报导', '行业报道'), ('产业数据', '行业数据'), ('实际运转', '实际运行'),
    ('报导', '报道'), ('塑胶', '塑料'), ('滑鼠', '鼠标'), ('视窗', '窗口'),
    ('「', '“'), ('」', '”'),  # 大陸用彎引號
]
# 英文版的全形標點
EN_PUNCT = [('，', ', '), ('。', '. '), ('、', ', '), ('；', '; '), ('：', ': '), ('（', ' ('), ('）', ')'),
            ('「', '“'), ('」', '”'), ('＋', ' + '), ('＝', ' = '), ('／', '/'), ('｜', ' | ')]
# 英文版允許保留的中文（署名）
EN_KEEP = {'@Harry汪', 'By Harry汪'}

cc = opencc.OpenCC('t2s')
EN = json.loads((ROOT / 'i18n' / 'en.json').read_text(encoding='utf8'))
# 英文撇號一律用 ’，否則會截斷 JS 的單引號字串
EN = {k: v.replace("'", '’') for k, v in EN.items()}


def to_cn(text):
    out = cc.convert(text)
    for a, b in CN_FIX:
        out = out.replace(a, b)
    return out


def to_en(text, page):
    masked = strip_comments(text)
    parts, last, missing = [], 0, []
    for pos, seg in segments(masked):
        if seg in EN_KEEP:
            continue
        if seg not in EN:
            missing.append(seg); continue
        parts.append(text[last:pos]); parts.append(EN[seg]); last = pos + len(seg)
    parts.append(text[last:])
    if missing:
        raise SystemExit(f'{page}: en.json 缺少 {len(missing)} 段，例如：{missing[:5]}')
    out = ''.join(parts)
    for a, b in EN_PUNCT:
        out = out.replace(a, b)
    out = re.sub(r'(?<=\S) {2,}(?=\S)', ' ', out)
    left = [m.group() for m in re.finditer(r'[^\n]*[㐀-鿿][^\n]*', strip_comments(out))
            if not any(k in m.group() for k in EN_KEEP)]
    if left:
        raise SystemExit(f'{page}: 英文版仍有中文：{left[:3]}')
    return out


def en_patch(script):
    """英文版的提示框副標題改顯示中文原名。"""
    zh = {v: k for k, v in EN.items() if len(k) <= 12 and HAN.search(k)}
    script = script.replace('esc(L.e)', 'esc(__ZH[L.n]||L.e)').replace('esc(o.e)', 'esc(__ZH[o.n]||o.e)')
    return 'const __ZH=' + json.dumps(zh, ensure_ascii=False) + ';\n' + script


def split(src):
    i, j = src.index('<div class="page">'), src.index('<script>')
    k = src.index('</script>', j)
    return src[:i], src[i:j].rstrip(), src[j + 8:k]


LANGBAR_CSS = '''
/* 語言切換 */
html[lang="zh-Hans-CN"]{--font:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif}
html[lang="en-US"]{--font:"Inter","Noto Sans TC",system-ui,sans-serif}
.langrow{max-width:%s;margin:0 auto 10px;display:flex;justify-content:flex-end}
.langsw{display:inline-flex;gap:2px;padding:3px;border:1px solid var(--line);border-radius:999px;background:var(--surface)}
.langsw button{font-family:var(--font);font-size:12px;border:0;background:transparent;color:var(--muted);padding:4px 12px;border-radius:999px;cursor:pointer}
.langsw button[aria-pressed="true"]{background:var(--ink);color:var(--surface)}
.langsw button:focus-visible{outline:2px solid var(--muted);outline-offset:2px}
'''

LANGBAR = ('<div class="langrow"><div class="langsw" role="group" aria-label="語言 / 语言 / Language">'
           '<button type="button" data-l="zh-TW" lang="zh-Hant">繁中</button>'
           '<button type="button" data-l="zh-CN" lang="zh-Hans">简中</button>'
           '<button type="button" data-l="en" lang="en">EN</button></div></div>')

BOOT = '''<script>
/* 語言切換：換掉 #app 的內容並重新執行該語言的腳本，先前登記在 document/window 上的監聽一併移除 */
(function(){
  var HL=%s, TT=%s, app=document.getElementById('app'), rec=[], cur=null;
  var btns=[].slice.call(document.querySelectorAll('.langsw button'));
  function mount(l){
    if(!window.__APP[l]) l='zh-TW';
    rec.forEach(function(r){r[0].removeEventListener(r[1],r[2],r[3])}); rec=[];
    var D=document, W=window, add=EventTarget.prototype.addEventListener;
    D.addEventListener=function(t,f,o){rec.push([D,t,f,o]);return add.call(D,t,f,o)};
    W.addEventListener=function(t,f,o){rec.push([W,t,f,o]);return add.call(W,t,f,o)};
    document.documentElement.lang=HL[l];
    try{ app.replaceChildren(document.getElementById('t-'+l).content.cloneNode(true)); window.__APP[l](); }
    finally{ delete D.addEventListener; delete W.addEventListener; }
    document.title=TT[l]; cur=l;
    btns.forEach(function(b){b.setAttribute('aria-pressed',String(b.getAttribute('data-l')===l))});
    try{ localStorage.setItem('refinery-lang',l) }catch(e){}
  }
  btns.forEach(function(b){b.addEventListener('click',function(){var l=b.getAttribute('data-l');if(l!==cur)mount(l)})});
  var init='zh-TW'; try{ init=localStorage.getItem('refinery-lang')||init }catch(e){}
  mount(init);
})();
</script>'''


def build(page):
    src = (ROOT / 'src' / f'{page}.html').read_text(encoding='utf8')
    head, markup, script = split(src)
    title = re.search(r'<title>(.*?)</title>', head).group(1)
    variants = {'zh-TW': (markup, script, title),
                'zh-CN': (to_cn(markup), to_cn(script), to_cn(title)),
                'en': (to_en(markup, page), en_patch(to_en(script, page)), EN[title])}
    pagew = re.search(r'\.page\{max-width:([^;]+);', head).group(1)
    head = head.replace('&display=swap', '&family=Noto+Sans+SC:wght@300;400;500;700&family=Inter:wght@300;400;500;600;700&display=swap', 1)
    head = head.replace('</style>', LANGBAR_CSS % pagew + '</style>', 1)
    out = [head.rstrip(), LANGBAR, '<div id="app"></div>']
    for l in LANGS:
        out.append(f'<template id="t-{l}">\n{variants[l][0]}\n</template>')
    for l in LANGS:
        code = variants[l][1]
        assert '</script' not in code
        out.append(f'<script>\nwindow.__APP=window.__APP||{{}};\nwindow.__APP["{l}"]=function(){{\n{code}\n}};\n</script>')
    out.append(BOOT % (json.dumps(HTML_LANG), json.dumps({l: variants[l][2] for l in LANGS}, ensure_ascii=False)))
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    art = sys.argv[sys.argv.index('--artifact') + 1] if '--artifact' in sys.argv else None
    for p in PAGES:
        body = build(p)
        (ROOT / f'{p}.html').write_text('<!doctype html>\n<html lang="zh-Hant-TW">\n' + body, encoding='utf8')
        if art:
            pathlib.Path(art, f'{p}.html').write_text(body, encoding='utf8')
        print('built', p)
