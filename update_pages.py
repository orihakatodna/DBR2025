#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_pages.py
日本語MDとベンガル語MDを読み込み、DBR2025_pwa.html の PAGES を更新する

使い方:
    python update_pages.py japanese.md bengali.md DBR2025_pwa.html

出力:
    DBR2025_pwa_updated.html
"""

import sys, re, json, html as html_lib
from pathlib import Path

# ─── 数字変換 ────────────────────────────────────────────────
def to_ascii_num(s):
    s = s.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
    s = s.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    return s

def extract_page_num(marker):
    s = to_ascii_num(marker.strip().strip('*').strip())
    m = re.search(r'\d{4,6}', s)
    if m and m.group(0) != '2025':
        return m.group(0)
    return None

# ─── 見出しレベル対応 ────────────────────────────────────────
#  md ##(lv2)→h3/h-lv3  ###(lv3)→h4/h-lv4  ####(lv4)→h5/h-lv5  #####(lv5)→h6/h-lv6
HEADING_TAG   = {2:'h3', 3:'h4', 4:'h5', 5:'h6'}
HEADING_CLASS = {2:'h-lv3', 3:'h-lv4', 4:'h-lv5', 5:'h-lv6'}

# ─── インライン変換 ──────────────────────────────────────────
def escape_inline(text):
    text = html_lib.escape(text, quote=False)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',         text)
    text = re.sub(r'`(.+?)`',       r'<span class="math">\1</span>', text)
    return text

# ─── テーブル変換 ────────────────────────────────────────────
def parse_table(table_lines):
    rows = []
    for line in table_lines:
        if re.match(r'^\|[-:| ]+\|$', line.strip()):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)
    if not rows:
        return ''
    h = '<div class="table-wrap"><table><thead><tr>'
    h += ''.join(f'<th>{escape_inline(c)}</th>' for c in rows[0])
    h += '</tr></thead>'
    if len(rows) > 1:
        h += '<tbody>'
        for row in rows[1:]:
            h += '<tr>' + ''.join(f'<td>{escape_inline(c)}</td>' for c in row) + '</tr>'
        h += '</tbody>'
    h += '</table></div>'
    return h

# ─── 1行 → HTML ─────────────────────────────────────────────
def md_line_to_html(line):
    # 図タイトル（চিত্র 等の単独行）── 見出し処理より先にチェック
    if re.match(r'^#{2,6}\s+(চিত্র|চিত্রসমূহ|Figure|図)\s*$', line.rstrip()):
        txt = line.lstrip('#').strip()
        return f'<p class="fig-title">{html_lib.escape(txt)}</p>'
    # ## 以上の見出し（# はページ区切りなので除外）
    m = re.match(r'^(#{2,6})\s+(.*)', line)
    if m:
        lv  = len(m.group(1))
        txt = escape_inline(m.group(2).strip())
        tag = HEADING_TAG.get(lv, 'h6')
        cls = HEADING_CLASS.get(lv, 'h-lv6')
        return f'<{tag} class="{cls}">{txt}</{tag}>'
    if re.match(r'^---+\s*$', line.strip()):
        return '<hr class="sep">'
    if line.strip() == '':
        return ''
    # 画像 ![alt](path)
    m = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)\s*$', line.strip())
    if m:
        alt  = html_lib.escape(m.group(1), quote=True)
        src  = html_lib.escape(m.group(2), quote=True)
        return (f'<figure class="fig-wrap">'
                f'<img src="{src}" alt="{alt}" class="fig-img">'
                f'<figcaption class="fig-caption">{alt}</figcaption>'
                f'</figure>')
    m = re.match(r'^[-*]\s+(.*)', line)
    if m:
        return f'<p class="list-item">・{escape_inline(m.group(1).strip())}</p>'
    m = re.match(r'^\d+\.\s+(.*)', line)
    if m:
        return f'<p class="list-item">{escape_inline(m.group(1).strip())}</p>'
    return f'<p>{escape_inline(line.strip())}</p>'

# ─── 行リスト → HTML ────────────────────────────────────────
def lines_to_html(lines):
    parts = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # テーブル検出
        if ('|' in line and i + 1 < len(lines) and
                re.match(r'^\|[-:| ]+\|', lines[i+1].strip())):
            tbl = []
            while i < len(lines) and '|' in lines[i]:
                tbl.append(lines[i]); i += 1
            parts.append(parse_table(tbl))
            continue
        r = md_line_to_html(line)
        if r:
            parts.append(r)
        i += 1
    return '\n'.join(parts)

# ─── MD → ページ辞書 ────────────────────────────────────────
def parse_md(md_text):
    """{ page_num: lines } の辞書と出現順リストを返す"""
    lines = md_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    blocks = []
    cur_marker, cur_lines = None, []
    for line in lines:
        if re.match(r'^#(?!#)\s+', line):
            if cur_marker is not None:
                blocks.append((cur_marker, cur_lines))
            cur_marker = line.strip()
            cur_lines  = []
        else:
            cur_lines.append(line)
    if cur_marker is not None:
        blocks.append((cur_marker, cur_lines))

    page_dict  = {}
    page_order = []
    for marker, block_lines in blocks:
        num = extract_page_num(marker)
        if not num:
            continue
        if num not in page_order:
            page_order.append(num)
        page_dict[num] = block_lines

    return page_dict, page_order

# ─── PAGES配列生成 ──────────────────────────────────────────
def build_pages(jp_dict, bn_dict, jp_order):
    pages = []
    for num in jp_order:
        jp_html = lines_to_html(jp_dict.get(num, []))
        bn_html = lines_to_html(bn_dict.get(num, []))
        pages.append({'num': num, 'jp': jp_html, 'bn': bn_html})
    return pages

# ─── HTML更新（文字列スライスで安全に置換）────────────────────
def update_html(html_path, pages):
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    m = re.search(r'const PAGES\s*=\s*\[.*?\];', html, flags=re.DOTALL)
    if not m:
        print('警告: PAGES配列が見つかりませんでした。')
        return html

    new_js = ('const PAGES = ' +
              json.dumps(pages, ensure_ascii=False, separators=(',', ':')) +
              ';')
    updated = html[:m.start()] + new_js + html[m.end():]
    print(f'✓ PAGES配列を {len(pages)} ページのデータで更新しました。')
    return updated

# ─── メイン ──────────────────────────────────────────────────
def main():
    if len(sys.argv) < 4:
        print('使い方: python update_pages.py japanese.md bengali.md DBR2025_pwa.html')
        sys.exit(1)

    jp_path, bn_path, html_path = sys.argv[1], sys.argv[2], sys.argv[3]
    for p in [jp_path, bn_path, html_path]:
        if not Path(p).exists():
            print(f'エラー: {p} が見つかりません'); sys.exit(1)

    print(f'読み込み中: {jp_path}')
    with open(jp_path, 'r', encoding='utf-8') as f:
        jp_text = f.read()

    print(f'読み込み中: {bn_path}')
    with open(bn_path, 'r', encoding='utf-8') as f:
        bn_text = f.read()

    print('変換中...')
    jp_dict, jp_order = parse_md(jp_text)
    bn_dict, _        = parse_md(bn_text)

    # ページ番号の一致確認
    jp_set = set(jp_order)
    bn_set = set(bn_dict.keys())
    only_jp = jp_set - bn_set
    only_bn = bn_set - jp_set
    if only_jp: print(f'  注意: JP のみ存在するページ: {sorted(only_jp)}')
    if only_bn: print(f'  注意: BN のみ存在するページ: {sorted(only_bn)}')

    pages = build_pages(jp_dict, bn_dict, jp_order)
    print(f'  → {len(pages)} ページ生成')

    # サンプル表示
    for p in pages[:3]:
        jp_h = re.findall(r'class="h-lv\d">(.*?)</', p['jp'])
        bn_h = re.findall(r'class="h-lv\d">(.*?)</', p['bn'])
        print(f'  page {p["num"]}:')
        if jp_h: print(f'    JP: {jp_h[0][:55]}')
        if bn_h: print(f'    BN: {bn_h[0][:55]}')

    print(f'更新中: {html_path}')
    updated = update_html(html_path, pages)

    out_path = Path(html_path).stem + '_updated.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(updated)
    print(f'✓ 完成: {out_path}')

if __name__ == '__main__':
    main()
