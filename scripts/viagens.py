"""Viagens a serviço (SCDP) das UGs da SDR · Portal da Transparência.
O Portal publica um zip por ano com a data no nome (ex.: viagens/2026_20261110_Viagens.zip): o robô procura o mais recente.
Uma viagem é nossa quando as diárias foram pagas por uma das UGs abaixo (passagens e seguro são pagos de forma central pela 130005).
Uso: python scripts/viagens.py SAIDA   ->  SAIDA/viagens/viagens_ANO.json
"""
import csv, datetime, io, json, os, sys, zipfile
sys.path.insert(0, os.path.dirname(__file__))
from historico_portal import CDN, baixar, log

UGS = {'130010', '130141', '130255', '135098', '420013'}
UF = {'Acre': 'AC', 'Alagoas': 'AL', 'Amapá': 'AP', 'Amazonas': 'AM', 'Bahia': 'BA', 'Ceará': 'CE', 'Distrito Federal': 'DF', 'Espírito Santo': 'ES',
      'Goiás': 'GO', 'Maranhão': 'MA', 'Mato Grosso': 'MT', 'Mato Grosso do Sul': 'MS', 'Minas Gerais': 'MG', 'Pará': 'PA', 'Paraíba': 'PB', 'Paraná': 'PR',
      'Pernambuco': 'PE', 'Piauí': 'PI', 'Rio de Janeiro': 'RJ', 'Rio Grande do Norte': 'RN', 'Rio Grande do Sul': 'RS', 'Rondônia': 'RO', 'Roraima': 'RR',
      'Santa Catarina': 'SC', 'São Paulo': 'SP', 'Sergipe': 'SE', 'Tocantins': 'TO'}
PEQ = {'De', 'Da', 'Do', 'Das', 'Dos', 'E'}


def num(x):
    try: return float(str(x or '0').replace('.', '').replace(',', '.') or 0)
    except ValueError: return 0.0


def titulo(s):
    s = (s or '').strip()
    return ' '.join(w if i == 0 or w not in PEQ else w.lower() for i, w in enumerate(s.title().split()))


def achar_zip(ano, hoje):
    """Tenta as datas de hoje para trás (o nome do arquivo traz a data da geração)."""
    for d in range(0, 40):
        dt = hoje - datetime.timedelta(days=d)
        url = f'{CDN}viagens/{ano}_{dt:%Y%m%d}_Viagens.zip'
        z = baixar(url, tentativas=2)
        if isinstance(z, bytes):
            log(f'  viagens {ano}: {url.rsplit("/", 1)[1]} ({len(z) / 1048576:.1f} MB)')
            return z, dt
    return None, None


def ler(z, nome):
    n = next((x for x in z.namelist() if x.endswith(nome)), None)
    if not n: return []
    txt = z.read(n).decode('latin1')
    r = csv.reader(io.StringIO(txt), delimiter=';')
    cab = [c.strip() for c in next(r)]
    return [dict(zip(cab, l)) for l in r]


def lugar(pais, uf, cid):
    if pais and pais != 'Brasil': return cid, '', True
    s = UF.get(uf, '')
    return (cid + '/' + s) if s else cid, s, False


def processar(zb, ano):
    z = zipfile.ZipFile(io.BytesIO(zb))
    pag = {}
    for r in ler(z, '_Pagamento.csv'):
        ug = r.get('Código da unidade gestora pagadora', '').strip()
        if ug in UGS and 'DI' in r.get('Tipo de pagamento', '').upper():
            pag.setdefault(r['Identificador do processo de viagem'], ug)
    log(f'  viagens {ano}: {len(pag)} com diárias pagas pelas UGs SDR')
    tre, pas = {}, {}
    for r in ler(z, '_Trecho.csv'):
        i = r.get('Identificador do processo de viagem', '').strip()
        if i in pag: tre.setdefault(i, []).append(r)
    for r in ler(z, '_Passagem.csv'):
        i = r['Identificador do processo de viagem']
        if i in pag: pas.setdefault(i, []).append(r)
    out = []
    for r in ler(z, '_Viagem.csv'):
        i = r['Identificador do processo de viagem']
        if i not in pag: continue
        tr = sorted(tre.get(i, []), key=lambda t: int(t.get('Sequência Trecho') or 0))
        orig = destC = destUF = ''; ext = False
        if tr:
            t0 = tr[0]
            tm = next((t for t in tr if t.get('Missao?', '').strip().lower().startswith('s')), t0)     # trecho da missão = destino principal
            orig = lugar(t0['Origem - País'], t0['Origem - UF'], t0['Origem - Cidade'])[0]
            destC, destUF, ext = lugar(tm['Destino - País'], tm['Destino - UF'], tm['Destino - Cidade'])
            ext = ext or any(t['Destino - País'] not in ('Brasil', '') for t in tr)
        ps = pas.get(i, [])
        out.append({'ug': pag[i], 'pcdp': r['Número da Proposta (PCDP)'], 'sit': r['Situação'], 'urg': r['Viagem Urgente'],
                    'just': r['Justificativa Urgência Viagem'].strip(), 'nome': titulo(r['Nome']), 'cargo': titulo(r['Cargo']) or 'Sem Cargo Informado',
                    'ini': r['Período - Data de início'], 'fim': r['Período - Data de fim'], 'dest': r['Destinos'], 'motivo': r['Motivo'][:200],
                    'diar': num(r['Valor diárias']), 'pass': num(r['Valor passagens']), 'dev': num(r['Valor devolução']), 'outros': num(r['Valor outros gastos']),
                    'orig': orig, 'ext': ext, 'destC': destC, 'destUF': destUF, 'emis': [p['Data da emissão/compra'] for p in ps],
                    'ndi': round(sum(num(t.get('Número Diárias')) for t in tr), 2), 'taxa': round(sum(num(p['Taxa de serviço']) for p in ps), 2)})
    out.sort(key=lambda d: d['ini'][6:] + d['ini'][3:5] + d['ini'][:2])
    return out


def main():
    saida = sys.argv[1] if len(sys.argv) > 1 else 'saida'
    pasta = os.path.join(saida, 'viagens'); os.makedirs(pasta, exist_ok=True)
    hoje = datetime.date.today()
    anos = [hoje.year] + ([hoje.year - 1] if hoje.month <= 2 else [])
    for ano in anos:
        zb, dt = achar_zip(ano, hoje)
        if not zb:
            log(f'  viagens {ano}: arquivo não encontrado no Portal'); continue
        lin = processar(zb, ano)
        json.dump({'ano': ano, 'posicao': f'{dt:%d/%m/%Y}', 'fonte': 'Portal da Transparência · Viagens a Serviço', 'ugs': sorted(UGS), 'viagens': lin},
                  open(os.path.join(pasta, f'viagens_{ano}.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        log(f'  viagens {ano}: {len(lin)} viagens gravadas')


if __name__ == '__main__':
    main()
