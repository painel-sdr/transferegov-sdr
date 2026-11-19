"""Captação de Emendas · Emenda Individual
Lê os extratores do SIOP (config/siop/emendas_AAAA.csv, um por ano) e cruza com o Transferegov
(propostas, instrumentos e empenhos que o robô já baixou), pelo nº da emenda + CNPJ do beneficiário.
Só as ações das 5 UGs da SDR (130010, 130141, 130255, 135098 e 420013).
Saída: emendas_siop.json  {gerado_em, anos, linhas:[...uma por beneficiário], emendas:[...uma por emenda]}
Uso: python scripts/emendas_siop.py saida
"""
import csv, datetime, glob, gzip, io, json, os, re, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ACOES = {'20ZV', '2000', '20ZY', '215A', '8593', '214Z', '00PN', '8622', '21B6', '8606'}
AREA = {'8593': 'DEPROS', '8622': 'DECAP', '215A': 'DECAP', '214Z': 'DEPROS', '21B6': 'DECAP', '8606': 'DECAP', '00PN': 'SDR', '20ZY': 'CEPLAC', '2000': 'SDR'}
AREA_UG = {'130141': 'CGPI', '130255': 'PROMAQ', '135098': 'CGPI', '130010': 'CEPLAC'}
MA = {'30': ('Convênio', 'Estado'), '31': ('Convênio', 'Estado'), '40': ('Convênio', 'Município'), '41': ('Convênio', 'Município'),
      '50': ('Termo de Fomento', 'OSC'), '90': ('Aplicação direta', 'Órgão federal'), '91': ('Aplicação direta', 'Órgão federal'), '99': ('A definir', '—')}
UF = {'11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA', '16': 'AP', '17': 'TO', '21': 'MA', '22': 'PI', '23': 'CE', '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE',
      '29': 'BA', '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP', '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT', '52': 'GO', '53': 'DF'}
f = lambda v: float(str(v or '0').replace(',', '.') or 0)
dig = lambda s: re.sub(r'\D', '', str(s or ''))


def ler_csv(caminho):
    if not os.path.exists(caminho):
        return []
    abre = gzip.open if caminho.endswith('.gz') else open
    with abre(caminho, 'rt', encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def main(saida):
    linhas_siop = []
    for arq in sorted(glob.glob(os.path.join(AQUI, '..', 'config', 'siop', 'emendas_*.csv'))):
        linhas_siop += ler_csv(arq)
    print(f'SIOP: {len(linhas_siop)} linhas lidas', flush=True)
    # Transferegov (o que o robô já baixou nesta rodada)
    props = ler_csv(os.path.join(saida, 'propostas.csv.gz')) or ler_csv(os.path.join(saida, 'propostas.csv'))
    insts = {r['nr_instrumento']: r for r in (ler_csv(os.path.join(saida, 'instrumentos.csv.gz')) or ler_csv(os.path.join(saida, 'instrumentos.csv')))}
    emps = {}
    for r in ler_csv(os.path.join(saida, 'empenhos.csv.gz')) or ler_csv(os.path.join(saida, 'empenhos.csv')):
        emps.setdefault(r['NR_CONVENIO'], []).append(r)
    porEmenda = {}
    # propostas (o robô baixa as de 2023 em diante) + instrumentos (todos os anos, trazem a proposta de origem)
    vistos = {p.get('id_proposta') for p in props}
    props = props + [r for r in insts.values() if r.get('id_proposta') not in vistos]
    for p in props:
        for n in (p.get('nr_emenda') or '').split(' | '):
            if n.strip():
                porEmenda.setdefault((p.get('ano_proposta', ''), n.strip().lstrip('0'), dig(p.get('cnpj_proponente'))), []).append(p)

    vistos_inst, vistos_ne = set(), set()
    # impedimento e tramitação (extrator com 'Valor Impedido/Tramitando (por Beneficiário)' e 'Tipo Impedimento'): o SIOP põe
    # numa linha à parte do mesmo beneficiário (indicado 0) · junta tudo na linha do beneficiário (emenda + CNPJ + GND + modalidade)
    imp = {}
    for r in linhas_siop:
        cn = dig(r.get('Beneficiário'))
        if not cn:
            continue
        k = ((r.get('Número Emenda') or '').strip(), cn, (r.get('GND') or '').strip(), (r.get('Modalidade') or '').strip())
        o = imp.setdefault(k, dict(impedido=0.0, tramitando=0.0, tipos=set(), ind=0.0))
        o['impedido'] += f(r.get('Valor Impedido (por Beneficiário)')); o['tramitando'] += f(r.get('Valor Tramitando (por Beneficiário)')); o['ind'] += f(r.get('Valor Indicado (por Beneficiário)'))
        t = (r.get('Tipo Impedimento') or '').strip()
        if t and t.upper() not in ('NÃO SE APLICA', 'NAO SE APLICA', '-', '--'):
            o['tipos'].add(t)
    em = {}      # nº da emenda → resumo (dotação: autorizado, empenhado, disponível)
    ben = []     # uma linha por beneficiário
    for r in linhas_siop:
        acao = (r.get('Ação') or '').strip().upper()
        num = (r.get('Número Emenda') or '').strip()
        if acao not in ACOES or not num.strip('0'):
            continue
        ano = (r.get('Ano Exercício') or num[:4]).strip()
        autor = (r.get('Autor (nome)') or '').strip()
        cod_autor, nome_autor = (autor.split(' - ', 1) + [''])[:2] if ' - ' in autor else ('', autor)
        loc = (r.get('Localizador') or '').strip()
        uf = UF.get(loc[-2:], 'Nacional' if loc in ('0001', '') else loc)
        e = em.setdefault(num, dict(ano=ano, emenda=num, autor=nome_autor.strip(), cod_autor=cod_autor.strip(), partido=(r.get('Partido (sigla)') or '').strip(),
                                    acao=acao, acao_nome=(r.get('Ação (desc.)') or '').split(' - ', 1)[-1].strip(), uf=uf, autorizado=0.0, empenhado_siop=0.0, disponivel=0.0, indicado=0.0, beneficiarios=0,
                                    bloqueado=0.0, impedido=0.0, tramitando=0.0, tem_imp='Valor Impedido (por Beneficiário)' in r))
        e['autorizado'] += f(r.get('Autorizado')); e['empenhado_siop'] += f(r.get('Empenhado')); e['disponivel'] += f(r.get('Disponível*'))
        e['bloqueado'] += f(r.get('Valor Bloqueado da Emenda')); e['impedido'] += f(r.get('Valor Impedido (por Beneficiário)')); e['tramitando'] += f(r.get('Valor Tramitando (por Beneficiário)'))
        cnpj = dig(r.get('Beneficiário'))
        vind = f(r.get('Valor Indicado (por Beneficiário)'))
        if not cnpj and not vind:
            continue
        ki = (num, cnpj, (r.get('GND') or '').strip(), (r.get('Modalidade') or '').strip())
        I = imp.get(ki) or dict(impedido=0.0, tramitando=0.0, tipos=set(), ind=0.0)
        if not vind and I['ind'] > 0:
            continue      # linha só de impedimento/tramitação: o valor já vai na linha do beneficiário (abaixo)
        if I.get('usado'):
            I = dict(impedido=0.0, tramitando=0.0, tipos=set(), ind=0.0)   # mesmo beneficiário em duas linhas com indicado: o impedimento entra na primeira
        else:
            imp.get(ki, {})['usado'] = True
        e['indicado'] += vind; e['beneficiarios'] += 1
        ma = (r.get('Modalidade') or '').strip()
        mod, tp = MA.get(ma, ('—', '—'))
        gnd = (r.get('GND') or '').strip()
        nome_ben = (r.get('Beneficiário (nome)') or '').split(' - ', 1)[-1].strip()
        # Transferegov: proposta do mesmo ano, mesma emenda (sem o ano na frente) e mesmo CNPJ
        ps = porEmenda.get((ano, num[4:].lstrip('0'), cnpj), [])
        if not ps:
            ps = [p for k, L in porEmenda.items() if k[1] == num[4:].lstrip('0') and k[2] == cnpj for p in L]
        ps = sorted(ps, key=lambda p: (p.get('nr_instrumento') == '', p.get('nr_proposta', '')))
        p = ps[0] if ps else {}
        pm = (p.get('modalidade') or '').strip().upper()
        if pm:   # a modalidade de verdade é a da proposta no Transferegov (o MA 90 do SIOP às vezes vira convênio/termo depois)
            mod = {'CONVENIO': 'Convênio', 'TERMO DE FOMENTO': 'Termo de Fomento', 'CONTRATO DE REPASSE': 'Contrato de Repasse', 'TERMO DE COLABORACAO': 'Termo de Colaboração'}.get(pm, pm.title())
        nj = (p.get('natureza_juridica') or '').upper()
        if nj:
            tp = 'Município' if 'MUNICIPAL' in nj else 'Estado' if 'ESTADUAL' in nj or 'DISTRITO' in nj else 'OSC' if 'SOCIEDADE CIVIL' in nj or 'PRIVAD' in nj or 'ENTIDADE' in nj else 'Consórcio' if 'CONS' in nj else tp
        ni = (p.get('nr_instrumento') or '').strip()
        it = insts.get(ni, {})
        nes = emps.get(ni, [])
        cod = num[4:].lstrip('0')
        daEm = [x for x in nes if cod and (cod in (x.get('PLANO_INTERNO') or '') or cod in (x.get('DESCRICAO_EMENDA_SIAFI') or ''))]   # a nota é desta emenda (PI I13390014 ou descrição da emenda no SIAFI)
        nes = daEm if daEm else ([] if len({e for e in (p.get('nr_emenda') or '').split(' | ') if e.strip()}) > 1 else nes)   # instrumento com várias emendas: só as notas da emenda
        nesG = [x for x in nes if str(x.get('NATUREZA_DESPESA', '')).startswith(gnd)] if gnd else nes   # custeio (3) e investimento (4) da mesma proposta ficam em linhas separadas
        nes = nesG or ([] if ni in vistos_inst else nes)
        nes = [x for x in nes if (ni, x.get('NR_EMPENHO'), x.get('ID_EMPENHO')) not in vistos_ne]   # cada nota conta uma vez só (a mesma entidade pode vir em várias linhas do SIOP)
        vistos_ne.update((ni, x.get('NR_EMPENHO'), x.get('ID_EMPENHO')) for x in nes)
        primeiro = ni and ni not in vistos_inst
        if ni:
            vistos_inst.add(ni)
        proc = dig(it.get('nr_processo'))
        proc = f'{proc[:5]}.{proc[5:11]}/{proc[11:15]}-{proc[15:17]}' if len(proc) == 17 else (it.get('nr_processo') or '')
        ug = (it.get('ug_emitente') or p.get('ug_emitente') or '').strip()
        ben.append(dict(
            ano=ano, emenda=num, autor=e['autor'], partido=e['partido'], acao=acao, area=(AREA_UG.get(ug) or ('SDR' if acao == '20ZV' else '')) if acao == '20ZV' else AREA.get(acao, ''),
            modalidade=mod, ma=ma, tp_entidade=tp, gnd=gnd, tipo_despesa={'3': 'Custeio', '4': 'Investimento', '5': 'Inversão financeira'}.get(gnd, gnd),
            programa=(p.get('cod_programa') or p.get('id_programa') or '').strip(), cnpj=cnpj if len(cnpj) == 14 else (r.get('Beneficiário') or '').strip(), entidade=nome_ben, uf=e['uf'],
            indicado=round(vind, 2), proposta=(p.get('nr_proposta') or '').strip(), situacao=(it.get('situacao') or p.get('situacao_proposta') or ('Aplicação direta (MAPA)' if ma.startswith('9') else 'Sem proposta no Transferegov' if cnpj else '')).strip(),
            instrumento=ni, processo=proc, ug=ug,
            pi=' / '.join(sorted({x.get('PLANO_INTERNO', '') for x in nes} - {''})), ptres=' / '.join(sorted({x.get('PTRES', '') for x in nes} - {''})),
            nd=' / '.join(sorted({x.get('NATUREZA_DESPESA', '') for x in nes} - {''})), ne=' / '.join(sorted({x.get('NR_EMPENHO', '') for x in nes} - {''})),
            impedido=round(I['impedido'], 2), tramitando=round(I['tramitando'], 2), tipo_impedimento=' | '.join(sorted(I['tipos'])),
            empenhado=round(sum(f(x.get('VALOR_EMPENHO')) for x in nes), 2), desembolsado=round(f(it.get('valor_desembolsado')), 2) if primeiro else 0.0,   # o desembolso é do instrumento: conta uma vez só
            link=(p.get('link_proposta') or '').strip()))
    for e in em.values():
        for k in ('autorizado', 'empenhado_siop', 'disponivel', 'indicado', 'bloqueado', 'impedido', 'tramitando'):
            e[k] = round(e[k], 2)
    out = dict(gerado_em=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M'),
               anos=sorted({e['ano'] for e in em.values()}), emendas=sorted(em.values(), key=lambda e: (e['ano'], e['emenda'])), linhas=ben)
    with open(os.path.join(saida, 'emendas_siop.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
    lig = sum(1 for b in ben if b['proposta'])
    print(f'Emendas SIOP: {len(em)} emendas, {len(ben)} beneficiários, {lig} ligados a proposta do Transferegov', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
