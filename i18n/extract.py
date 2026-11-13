"""從 src/ 的繁體原稿抽出需要翻譯的中文片段（排除代碼註釋）。"""
import re, sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
PAT = re.compile(r"[^'\"`<>{}\[\]\n=;:,()$|]*[㐀-鿿＀-￯　-〿][^'\"`<>{}\[\]\n=;$|]*")
HAN = re.compile(r'[㐀-鿿]')
COMMENT = re.compile(r'/\*.*?\*/|^\s*//[^\n]*|(?<=[;{}),])\s*//[^\n]*', re.S | re.M)

def strip_comments(s):
    return COMMENT.sub(lambda m: ' ' * len(m.group()), s)

def segments(text):
    for m in PAT.finditer(text):
        raw = m.group()
        core = raw.strip()
        if HAN.search(core):
            yield m.start() + (len(raw) - len(raw.lstrip())), core

if __name__ == '__main__':
    seen, out = set(), []
    for f in sorted((ROOT / 'src').glob('*.html')):
        body = strip_comments(f.read_text(encoding='utf8'))
        for _, seg in segments(body):
            if seg not in seen:
                seen.add(seg); out.append(seg)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=0)
