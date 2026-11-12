"""Carga histórica do Portal da Transparência (uma vez por ano; os anos fechados não mudam mais).
Guarda só as UGs da SDR. Uso:
  python scripts/historico_portal.py despesas ANO SAIDA     -> empenhos, liquidações e pagamentos do ano (arquivos diários)
  python scripts/historico_portal.py mensal   ANO SAIDA     -> execução da despesa e compras (arquivos mensais)
  python scripts/historico_portal.py orcamento ANO SAIDA    -> orçamento da despesa do MAPA (arquivo anual)
"""
import csv, datetime, io, os, sys, time, urllib.request, zipfile

CDN = 'https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/'
UGS = {'130010', '130141', '130255', '135098', '420013', '130005'}   # 130005 (CGOEF/SE): notas usadas em contratos da 130141 e 130255
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'}
csv.field_size_limit(10**9)
LOG = []


def log(m):
    m = time.strftime('%H:%M:%S') + '  ' + m
    print(m, flush=True)
    LOG.append(m)


def baixar(url, tentativas=6):
    espera = 5
    for t in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
                d = r.read()
                return d if d[:2] == b'PK' else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 403 and t >= 1:      # arquivo inexistente costuma vir como 403
                return None
            log(f'    {e.code} em {url.rsplit("/", 1)[1]} · nova tentativa em {espera}s')
        except Exception as e:
            log(f'    erro {str(e)[:80]} · nova tentativa em {espera}s')
        time.sleep(espera)
        espera = min(espera * 2, 120)
    log(f'  FALHOU: {url}')
    return 'falhou'


def linhas(z, nome):
    with z.open(nome) as f:
        rd = csv.reader(io.TextIOWrapper(f, encoding='latin-1', newline=''), delimiter=';')
        cab = next(rd, [])
        yield cab
        yield from rd


class Saida:
    def __init__(self, pasta, anexar=False):
        self.pasta = pasta
        self.arq = {}
        self.anexar = anexar   # refazer dias que falharam: acrescenta no fim dos arquivos que já existem
        os.makedirs(pasta, exist_ok=True)

    def gravar(self, nome, cab, rows):
        if nome not in self.arq:
            c = os.path.join(self.pasta, nome)
            ja = self.anexar and os.path.exists(c) and os.path.getsize(c) > 0
            f = open(c, 'a' if ja else 'w', newline='', encoding='utf-8')
            w = csv.writer(f)
            if not ja:
                w.writerow(cab)
            self.arq[nome] = (f, w, cab)
        f, w, c0 = self.arq[nome]
        for r in rows:
            w.writerow(r)

    def fechar(self):
        for f, _, _ in self.arq.values():
            f.close()


def idx(cab, *nomes):
    up = [c.strip().upper() for c in cab]
    for n in nomes:
        if n.upper() in up:
            return up.index(n.upper())
    return None


def despesas(ano, pasta, dias=None):
    out = Saida(pasta, anexar=dias is not None)
    d = datetime.date(ano, 1, 1)
    fim = min(datetime.date(ano, 12, 31), datetime.date.today() - datetime.timedelta(days=2))
    lista = dias if dias is not None else []
    if dias is None:
        while d <= fim:
            lista.append(d.strftime('%Y%m%d'))
            d += datetime.timedelta(days=1)
    n_dias = n_falhas = 0
    tot = {'emp': 0, 'liq': 0, 'pag': 0, 'liq_ne': 0, 'pag_ne': 0}
    for dia in lista:
        dados = baixar(f'{CDN}despesas/{dia}_Despesas.zip', tentativas=8 if dias is not None else 6)
        time.sleep(0.6 if dias is None else 20)   # refazendo: devagar, o Portal recusa quando vem pedido demais em seguida
        if dados == 'falhou':
            n_falhas += 1
            out.gravar('falhas.csv', ['dia'], [[dia]])
            continue
        if not dados:
            continue
        n_dias += 1
        z = zipfile.ZipFile(io.BytesIO(dados))
        nomes = z.namelist()
        cod_liq, cod_pag = set(), set()
        for tipo, sufixo in (('emp', '_Despesas_Empenho.csv'), ('liq', '_Despesas_Liquidacao.csv'), ('pag', '_Despesas_Pagamento.csv')):
            nome = next((n for n in nomes if n.endswith(sufixo)), None)
            if not nome:
                continue
            it = linhas(z, nome)
            cab = next(it)
            iu = idx(cab, 'Código Unidade Gestora')
            ic = idx(cab, {'emp': 'Código Empenho', 'liq': 'Código Liquidação', 'pag': 'Código Pagamento'}[tipo])
            sel = [r for r in it if iu is not None and iu < len(r) and r[iu].strip() in UGS]
            if tipo == 'liq' and ic is not None:
                cod_liq = {r[ic] for r in sel}
            if tipo == 'pag' and ic is not None:
                cod_pag = {r[ic] for r in sel}
            out.gravar(f'{tipo}_{ano}.csv', ['Dia arquivo'] + cab, ([dia] + r for r in sel))
            tot[tipo] += len(sel)
        # ligação pagamento/liquidação -> nota de empenho (o que cada documento abateu)
        for tipo, sufixo, cods in (('pag_ne', '_Despesas_Pagamento_EmpenhosImpactados.csv', cod_pag), ('liq_ne', '_Despesas_Liquidacao_EmpenhosImpactados.csv', cod_liq)):
            nome = next((n for n in nomes if n.endswith(sufixo)), None)
            if not nome or not cods:
                continue
            it = linhas(z, nome)
            cab = next(it)
            sel = [r for r in it if r and r[0] in cods]
            out.gravar(f'{tipo}_{ano}.csv', cab, sel)
            tot[tipo] += len(sel)
        if n_dias % 30 == 0:
            log(f'  {dia}: {n_dias} dias lidos · {tot}')
    out.fechar()
    log(f'despesas {ano}: {n_dias} dias com arquivo · {n_falhas} falhas · {tot}')


def mensal(ano, pasta):
    out = Saida(pasta)
    for m in range(1, 13):
        per = f'{ano}{m:02d}'
        if datetime.date(ano, m, 1) > datetime.date.today():
            break
        for base, arq, tag in (('despesas-execucao', f'{per}_Despesas.zip', 'execucao'), ('compras', f'{per}_Compras.zip', 'compras')):
            dados = baixar(CDN + base + '/' + arq)
            time.sleep(1)
            if not dados or dados == 'falhou':
                log(f'  {base} {per}: {"falhou" if dados == "falhou" else "sem arquivo"}')
                continue
            z = zipfile.ZipFile(io.BytesIO(dados))
            for nome in z.namelist():
                it = linhas(z, nome)
                cab = next(it)
                iu = idx(cab, 'Código Unidade Gestora', 'Código UG', 'Código Unidade Gestora Contratante', 'Código UG Contratante')
                if iu is None:
                    iu = next((i for i, c in enumerate(cab) if 'UNIDADE GESTORA' in c.upper() and 'CÓDIGO' in c.upper()), None)
                sel = [r for r in it if iu is not None and iu < len(r) and r[iu].strip() in UGS]
                parte = nome.split('_', 1)[1].rsplit('.', 1)[0] if '_' in nome else nome
                out.gravar(f'{tag}_{parte}_{ano}.csv', ['Mês arquivo'] + cab, ([per] + r for r in sel))
                log(f'  {base} {per} {nome}: {len(sel)} linhas das UGs')
    out.fechar()


def orcamento(ano, pasta):
    out = Saida(pasta)
    dados = baixar(f'{CDN}orcamento-despesa/{ano}_OrcamentoDespesa.zip')
    if not dados or dados == 'falhou':
        log(f'orçamento {ano}: sem arquivo')
        return
    z = zipfile.ZipFile(io.BytesIO(dados))
    for nome in z.namelist():
        it = linhas(z, nome)
        cab = next(it)
        io_ = next((i for i, c in enumerate(cab) if 'ÓRGÃO SUPERIOR' in c.upper() and 'CÓDIGO' in c.upper()), None)
        sel = [r for r in it if io_ is not None and io_ < len(r) and r[io_].strip() == '22000']
        out.gravar(f'orcamento_{ano}.csv', cab, sel)
        log(f'orçamento {ano} {nome}: {len(sel)} linhas do MAPA')
    out.fechar()


def falhas(ano, pasta):
    """Refaz só os dias que falharam (lista em falhas.csv) e acrescenta nos arquivos do ano que já existem."""
    c = os.path.join(pasta, 'falhas.csv')
    dias = [l.strip() for l in open(c, encoding='utf-8').read().split('\n')[1:] if l.strip()] if os.path.exists(c) else []
    log(f'falhas {ano}: {len(dias)} dias para refazer: {" ".join(dias)}')
    if not dias:
        return
    os.replace(c, os.path.join(pasta, 'falhas_anteriores.csv'))
    despesas(ano, pasta, dias)
    if not os.path.exists(c):
        open(c, 'w', encoding='utf-8').write('dia\n')


if __name__ == '__main__':
    tipo, ano, pasta = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    os.makedirs(pasta, exist_ok=True)
    {'despesas': despesas, 'mensal': mensal, 'orcamento': orcamento, 'falhas': falhas}[tipo](ano, pasta)
    open(os.path.join(pasta, f'log_{tipo}_{ano}.txt'), 'w').write('\n'.join(LOG))
