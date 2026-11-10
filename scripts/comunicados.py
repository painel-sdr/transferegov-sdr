"""Comunicados do MGI/Transferegov e da CMO + prazos dos cronogramas de emendas (para o Calendário de parcerias do painel).

Fontes (lidas todo dia pelo robô):
  - Transferegov · Comunicados gerais do ano
  - Transferegov · Cronogramas de emendas parlamentares (RP6 finalidade definida, RP6 transferência especial, RP7, RP8 ...)
  - Transferegov · Atualização de valores (TED e regime simplificado)
  - CMO · comunicados (republica instruções do Executivo e ofícios circulares da SRI)

As páginas do gov.br montam as listas por script; por isso a leitura tenta primeiro a API do próprio site (plone.restapi,
pedindo JSON) e, se não der, lê os links do HTML. Dos comunicados de cronograma, lê as tabelas de etapas e vira prazo.

Saída: saida/comunicados/comunicados.json  (+ comunicados_debug.txt para conferir o que cada fonte devolveu)
Nunca derruba o robô: qualquer erro fica registrado no JSON e o passo segue.
"""
import datetime, html, json, os, re, sys, urllib.parse, urllib.request
from html.parser import HTMLParser

ANO = datetime.date.today().year
UA = 'Mozilla/5.0 (Painel SDR 2026 - robo de dados abertos)'
TG = 'https://www.gov.br/transferegov/pt-br/comunicados'
FONTES = [
    ('Gerais', f'{TG}/comunicados-gerais/{ANO}'),
    ('Cronogramas de emendas', f'{TG}/cronogramas-de-emendas-parlamentares'),
    ('Atualização de valores', f'{TG}/atualizacao-de-valores'),
]
CMO = 'https://www.congressonacional.leg.br/web/cmo/comunicados'
DEBUG = []


def baixar(url, json_=False, tempo=40):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json' if json_ else 'text/html,*/*'})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        dado = r.read()
        tipo = r.headers.get('Content-Type', '')
    txt = dado.decode('utf-8', 'replace')
    if json_:
        if 'json' not in tipo and not txt.lstrip().startswith('{'):
            raise ValueError(f'não veio JSON ({tipo})')
        return json.loads(txt)
    return txt


def limpa(t):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t or ''))).strip()


def data_iso(v):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(v or ''))
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}' if m and m.group(1) != '1969' else ''


def numero(t):
    m = re.search(r'comunicado\s*n[\.ºo°]*\s*(\d{1,3})\s*/\s*(\d{4})', t or '', re.I) or re.search(r'of[ií]cio[^\d]{0,30}n[\.ºo°]*\s*(\d{1,3})\s*/\s*(\d{4})', t or '', re.I)
    return f'{int(m.group(1))}/{m.group(2)}' if m else ''


def tipo_de(url, titulo):
    t = (url + ' ' + (titulo or '')).lower()
    t = t.replace('ê', 'e').replace('ã', 'a').replace('ç', 'c').replace('ó', 'o')
    if re.search(r'transferencias?[-_ ]especia', t):
        return 'RP6 transferência especial'
    if re.search(r'rp ?-?6|individua', t):
        return 'RP6'
    if re.search(r'rp ?-?7|bancada', t):
        return 'RP7 bancada'
    if re.search(r'rp ?-?8|comiss', t):
        return 'RP8 comissão'
    if re.search(r'rp ?-?9|relator', t):
        return 'RP9'
    return 'Comunicado MGI'


# ---------------------------------------------------------------- listagem no gov.br (Plone)
def listar_plone(url):
    """devolve [{titulo, link, data, tipo_plone}] de tudo o que está abaixo da pasta (documentos e arquivos)"""
    q = 'sort_on=effective&sort_order=reverse&b_size=500&metadata_fields=effective&metadata_fields=created&metadata_fields=modified'
    erros = []
    for u in (f'{url}/@search?{q}', f'{url}/++api++/@search?{q}', url):
        try:
            j = baixar(u, json_=True)
            itens = j.get('items') or []
            DEBUG.append(f'[{url}] JSON {u[len(url):] or "(pasta)"} -> {len(itens)} itens; chaves {sorted(j.keys())[:12]}')
            out = []
            for it in itens:
                tp = it.get('@type', '')
                if tp in ('Folder', 'Collection', 'Link') and u.endswith(q):
                    continue
                out.append({'titulo': limpa(it.get('title')), 'link': it.get('@id', ''), 'data': data_iso(it.get('effective')) or data_iso(it.get('created')),
                            'descricao': limpa(it.get('description'))[:300], 'tipo_plone': tp})
            if out:
                return out, 'api ' + (u[len(url):].split('?')[0] or 'pasta')
        except Exception as e:
            erros.append(f'{u[len(url):].split("?")[0] or "pasta"}: {str(e)[:120]}')
    # HTML: links para dentro da pasta
    t = baixar(url)
    DEBUG.append(f'[{url}] HTML {len(t)} bytes; erros JSON: {" | ".join(erros)}\n{t[:1500]}')
    caminho = urllib.parse.urlparse(url).path.rstrip('/')
    vistos, out = set(), []
    for m in re.finditer(r'<a[^>]+href="([^"#?]+)"[^>]*>(.*?)</a>', t, re.S | re.I):
        href, txt = urllib.parse.urljoin(url, m.group(1)), limpa(m.group(2))
        p = urllib.parse.urlparse(href).path.rstrip('/')
        if not p.startswith(caminho + '/') or href in vistos or len(txt) < 8:
            continue
        vistos.add(href)
        perto = t[m.end():m.end() + 400]
        d = re.search(r'(\d{2}/\d{2}/\d{4})', perto)
        out.append({'titulo': txt, 'link': href, 'data': d.group(1) if d else '', 'descricao': '', 'tipo_plone': 'html'})
    return out, 'html'


# ---------------------------------------------------------------- tabelas de etapas
class Tabelas(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tabs, self.lin, self.cel, self.dentro = [], None, None, 0

    def handle_starttag(self, tag, a):
        if tag == 'table':
            self.dentro += 1
            self.tabs.append([])
        elif tag == 'tr' and self.dentro:
            self.lin = []
        elif tag in ('td', 'th') and self.lin is not None:
            self.cel = []
        elif tag == 'br' and self.cel is not None:
            self.cel.append(' ')

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cel is not None and self.lin is not None:
            self.lin.append(re.sub(r'\s+', ' ', ''.join(self.cel)).strip())
            self.cel = None
        elif tag == 'tr' and self.lin is not None:
            if any(self.lin) and self.tabs:
                self.tabs[-1].append(self.lin)
            self.lin = None
        elif tag == 'table':
            self.dentro = max(0, self.dentro - 1)

    def handle_data(self, d):
        if self.cel is not None:
            self.cel.append(d)


RX_DATA = re.compile(r'(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?:\s*/\s*(\d{2,4}))?(?!\d)')
RX_MES = re.compile(r'(?<!\d)(\d{1,2})\s*[ºo°]?\s*(?:de\s+)?(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-zç]*\.?(?:\s*(?:de\s+)?(\d{4}))?', re.I)
MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
RX_RESP = re.compile(r'autor|parlament|órg|orgao|setorial|mgi|mpo|sof|sri|benefici|conven|conced|proponen|bancada|comiss|ente', re.I)


def datas_da(txt, ano):
    ds = []
    for d, m, a in RX_DATA.findall(txt):
        d, m = int(d), int(m)
        if 1 <= d <= 31 and 1 <= m <= 12:
            a = int(a) if a else ano
            ds.append(f'{d:02d}/{m:02d}/{a + 2000 if a < 100 else a}')
    for d, m, a in RX_MES.findall(txt):
        d = int(d)
        if 1 <= d <= 31:
            ds.append(f'{d:02d}/{MESES.index(m.lower()[:3]) + 1:02d}/{a or ano}')
    return ds


def etapas(html_txt, ano):
    p = Tabelas()
    p.feed(html_txt or '')
    out = []
    for tab in p.tabs:
        for lin in tab:
            ds, cel_txt = [], []
            for c in lin:
                dc = datas_da(c, ano)
                ds += dc
                resto = RX_DATA.sub('', RX_MES.sub('', c)).strip(' -–aàté')
                if len(resto) > 3:
                    cel_txt.append(c)
            if not ds or not cel_txt:
                continue
            resp = next((c for c in cel_txt if RX_RESP.search(c) and len(c) < 70 and c != max(cel_txt, key=len)), '')
            ev = max(cel_txt, key=len)
            ini, fim = ds[0], (ds[-1] if len(ds) > 1 and ds[-1] != ds[0] else '')
            out.append({'data': ini, 'ate': fim, 'evento': ev[:240], 'resp': resp[:80]})
    return out


def conteudo(link):
    try:
        j = baixar(link, json_=True)
        t = (j.get('text') or {}).get('data') if isinstance(j.get('text'), dict) else j.get('text')
        if t:
            return t, j
    except Exception:
        pass
    t = baixar(link)
    m = re.search(r'id="(?:parent-fieldname-text|content-core)"[^>]*>(.*?)<footer', t, re.S)
    return (m.group(1) if m else t), {}


# ---------------------------------------------------------------- CMO (Liferay)
def cmo():
    t = baixar(CMO)
    DEBUG.append(f'[{CMO}] HTML {len(t)} bytes\n{t[:1200]}')
    vistos, out = set(), []
    for m in re.finditer(r'<a[^>]+href="([^"]*?/web/cmo/comunicados/-/blogs/[^"?#]+)[^"]*"[^>]*>(.*?)</a>', t, re.S | re.I):
        href, txt = urllib.parse.urljoin(CMO, html.unescape(m.group(1))), limpa(m.group(2))
        if href in vistos or len(txt) < 8:
            continue
        vistos.add(href)
        perto = limpa(t[max(0, m.start() - 600):m.end() + 600])
        d = re.search(r'(\d{2}/\d{2}/\d{2,4})', perto)
        dd = d.group(1) if d else ''
        if re.fullmatch(r'\d{2}/\d{2}/\d{2}', dd):
            dd = dd[:6] + '20' + dd[6:]
        out.append({'titulo': txt, 'link': href, 'data': dd})
    return out[:40]


def main(saida):
    os.makedirs(os.path.join(saida, 'comunicados'), exist_ok=True)
    res = {'gerado': datetime.datetime.now().strftime('%d/%m/%Y %H:%M'), 'ano': ANO, 'fontes': [], 'comunicados': [], 'prazos': []}
    vistos = set()
    for cat, url in FONTES:
        f = {'nome': cat, 'url': url}
        try:
            itens, metodo = listar_plone(url)
            f.update(metodo=metodo, ok=True)
            n = 0
            for it in itens:
                if it['link'] in vistos:
                    continue
                if cat == 'Cronogramas de emendas' and f'/{ANO}/' not in it['link'] + '/' and not it['data'].endswith(str(ANO)):
                    continue
                vistos.add(it['link'])
                n += 1
                res['comunicados'].append({'categoria': cat, 'data': it['data'], 'numero': numero(it['titulo'] + ' ' + it['link'].replace('-', ' ')),
                                           'titulo': it['titulo'], 'descricao': it['descricao'], 'link': it['link'], 'tipo': tipo_de(it['link'], it['titulo'])})
            f['qtd'] = n
        except Exception as e:
            f.update(ok=False, erro=str(e)[:200])
        res['fontes'].append(f)
        print(f"Comunicados · {cat}: {f.get('qtd', 0)} ({f.get('metodo') or f.get('erro')})", flush=True)
    f = {'nome': 'SRI/CMO', 'url': CMO}
    try:
        it = cmo()
        for x in it:
            res['comunicados'].append({'categoria': 'SRI/CMO', 'data': x['data'], 'numero': numero(x['titulo']), 'titulo': x['titulo'], 'descricao': '', 'link': x['link'], 'tipo': tipo_de(x['link'], x['titulo'])})
        f.update(ok=True, qtd=len(it), metodo='html')
    except Exception as e:
        f.update(ok=False, erro=str(e)[:200])
    res['fontes'].append(f)
    print(f"Comunicados · SRI/CMO: {f.get('qtd', 0)} ({f.get('metodo') or f.get('erro')})", flush=True)

    # etapas dos comunicados de cronograma do ano
    for c in res['comunicados']:
        if c['categoria'] != 'Cronogramas de emendas':
            continue
        try:
            corpo, j = conteudo(c['link'])
            if not c['data']:
                c['data'] = data_iso(j.get('effective')) if j else ''
            et = etapas(corpo, ANO)
            c['etapas_lidas'] = len(et)
            for e in et:
                res['prazos'].append({**e, 'tipo': c['tipo'], 'doc': ('Comunicado nº ' + c['numero']) if c['numero'] else c['titulo'][:80], 'link': c['link'], 'fonte': 'robô'})
            if not et:
                DEBUG.append(f'[sem tabela de etapas] {c["link"]}\n{limpa(corpo)[:600]}')
        except Exception as e:
            c['etapas_lidas'] = 0
            c['erro'] = str(e)[:160]

    def chave(c):
        d = c.get('data') or '01/01/1900'
        return d[6:10] + d[3:5] + d[:2]
    res['comunicados'].sort(key=chave, reverse=True)
    with open(os.path.join(saida, 'comunicados', 'comunicados.json'), 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(saida, 'comunicados', 'comunicados_debug.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n\n'.join(DEBUG))
    print(f"Comunicados: {len(res['comunicados'])} no total · {len(res['prazos'])} prazos lidos dos cronogramas", flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
