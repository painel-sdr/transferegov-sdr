"""Alertas por menu · Parcerias e TED (os de Gestão Contratual e Orçamento são calculados no painel, com os dados do navegador).
Cada alerta: {menu, sev ('r' crítico, 'y' atenção, 'b' acompanhar), id, titulo, sugestao, cols:[[campo, rótulo, tipo]], itens:[{campo: valor}]}
tipo: '' texto · 'n' valor em R$ · 'i' número inteiro · 'w' texto longo · 'inst' nº do instrumento (abre o relatório) · 'link' endereço
Saída: alertas.json  {gerado_em, hoje, parc:[...], ted:[...]}
Uso: python scripts/alertas.py saida
"""
import csv, datetime, gzip, json, os, re, sys

HOJE = datetime.date.today()
f = lambda v: float(str(v or '0').replace(',', '.') or 0) if re.match(r'^-?[\d.,]+$', str(v or '0').strip() or '0') else 0.0


def ler(caminho):
    if not os.path.exists(caminho):
        return []
    abre = gzip.open if caminho.endswith('.gz') else open
    with abre(caminho, 'rt', encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def data(s):
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', str(s or ''))
    return datetime.date(int(m[3]), int(m[2]), int(m[1])) if m else None


def item(num, nome, uf='', valor=0.0, info=''):
    return {'num': num, 'nome': (nome or '')[:90], 'uf': uf or '', 'valor': round(valor or 0, 2), 'info': info}


def alerta(menu, sev, id_, titulo, sugestao, itens, base=None, cols=None):
    return {'menu': menu, 'sev': sev, 'id': id_, 'titulo': titulo, 'sugestao': sugestao, 'itens': itens, 'base': base, 'cols': cols}


def proc_fmt(p):
    d = re.sub(r'\D', '', p or '')
    return f'{d[:5]}.{d[5:11]}/{d[11:15]}-{d[15:17]}' if len(d) == 17 else (p or '')


COL_INST = [['num', 'Instrumento', 'inst'], ['ano', 'Ano', ''], ['ug', 'UG responsável', ''], ['modalidade', 'Modalidade', ''], ['proponente', 'Convenente', ''], ['uf', 'UF', ''],
            ['municipio', 'Município', ''], ['acao', 'Ação', ''], ['programa', 'Programa', 'w'], ['processo', 'Processo', ''], ['objeto', 'Objeto', 'w'], ['situacao', 'Situação no Transferegov', ''],
            ['fim', 'Fim da vigência', ''], ['prazo_pc', 'Prazo da prestação de contas', ''], ['ult_des', 'Último desembolso', ''], ['ne', 'Notas de empenho', ''], ['info', 'Motivo do alerta', ''],
            ['repasse', 'Valor de repasse', 'n'], ['desembolsado', 'Desembolsado', 'n'], ['a_desembolsar', 'A desembolsar', 'n'], ['saldo', 'Saldo em conta', 'n']]
COL_PROP = [['num', 'Proposta', 'link'], ['ano', 'Ano', ''], ['ug', 'UG responsável', ''], ['modalidade', 'Modalidade', ''], ['proponente', 'Proponente', ''], ['cnpj', 'CNPJ', ''], ['uf', 'UF', ''],
            ['municipio', 'Município', ''], ['acao', 'Ação', ''], ['programa', 'Programa', 'w'], ['emenda', 'Emenda', ''], ['parlamentar', 'Parlamentar', ''], ['objeto', 'Objeto', 'w'],
            ['situacao', 'Situação da proposta', ''], ['info', 'Motivo do alerta', ''], ['valor', 'Valor de repasse', 'n'], ['global', 'Valor global', 'n']]
COL_EMENDA = [['num', 'Emenda', ''], ['ano', 'Ano', ''], ['autor', 'Autor', ''], ['partido', 'Partido', ''], ['acao', 'Ação', ''], ['ug', 'UG responsável', ''], ['area', 'Área', ''],
              ['entidade', 'Beneficiário', ''], ['cnpj', 'CNPJ', ''], ['uf', 'UF', ''], ['modalidade', 'Modalidade', ''], ['tipo', 'Tipo de despesa', ''], ['info', 'Motivo do alerta', ''], ['indicado', 'Valor indicado', 'n']]
COL_TED = [['num', 'Nº TED', ''], ['ano', 'Ano', ''], ['plano', 'Plano de ação', ''], ['sentido', 'Enviado / recebido', ''], ['ugdor', 'UG descentralizadora', ''], ['ugda', 'UG descentralizada', ''],
           ['unid', 'Unidade descentralizada', ''], ['processo', 'Processo', ''], ['acao', 'Ação', ''], ['objeto', 'Objeto', 'w'], ['situacao', 'Situação', ''], ['fim', 'Fim da vigência', ''],
           ['dias', 'Dias para o fim', 'i'], ['nc_lista', 'Notas de crédito', 'w'], ['info', 'Motivo do alerta', ''], ['firmado', 'Valor firmado', 'n'], ['nc', 'Descentralizado (NC)', 'n'],
           ['repassado', 'Repassado (PF)', 'n'], ['empenhado', 'Empenhado pela unidade', 'n'], ['pago', 'Pago pela unidade', 'n'], ['acomprovar', 'A comprovar', 'n']]


def parcerias(saida):
    inst = ler(os.path.join(saida, 'painel_instrumentos.csv'))
    obras = {r['nr_instrumento']: r for r in ler(os.path.join(saida, 'painel_obras.csv'))}
    grupos = {'parc': lambda r: r['ug_emitente'] == '130141', 'conv': lambda r: r['ug_emitente'] == '420013', 'repasse': lambda r: r['ug_emitente'] == '135098'}
    ATIVA = re.compile(r'Em execu|Aguardando Presta|Presta.*Complementa|Assinad|Proposta/Plano de Trabalho Aprovad', re.I)
    out = []
    for menu, filtro in grupos.items():
        n0 = len(out)
        L = [r for r in inst if filtro(r) and ATIVA.search(r.get('situacao') or '')]
        exe = [r for r in L if re.search(r'Em execu', r['situacao'], re.I)]
        dias = lambda r: (data(r['fim_vigencia']) - HOJE).days if data(r['fim_vigencia']) else None
        I = lambda r, info: {'num': r['nr_instrumento'], 'ano': r.get('ano', ''), 'ug': r.get('ug_emitente', ''), 'modalidade': r.get('modalidade', ''), 'proponente': r.get('proponente', ''),
                             'uf': r.get('uf', ''), 'municipio': r.get('municipio', ''), 'acao': (r.get('acao_orcamentaria') or '')[-4:], 'programa': r.get('programa', ''),
                             'processo': proc_fmt(r.get('nr_processo')), 'objeto': (r.get('objeto') or '')[:300], 'situacao': r.get('situacao', ''), 'fim': r.get('fim_vigencia', ''),
                             'prazo_pc': r.get('limite_prestacao_contas', ''), 'ult_des': r.get('ultimo_desembolso', ''), 'ne': r.get('notas_empenho', ''), 'info': info,
                             'repasse': round(f(r.get('valor_repasse')), 2), 'desembolsado': round(f(r.get('valor_desembolsado')), 2), 'a_desembolsar': round(f(r.get('valor_a_desembolsar')), 2),
                             'saldo': round(f(r.get('saldo_em_conta')), 2)}
        v_venc = [r for r in exe if dias(r) is not None and dias(r) < 0]
        v30 = [r for r in exe if dias(r) is not None and 0 <= dias(r) <= 30]
        v90 = [r for r in exe if dias(r) is not None and 30 < dias(r) <= 90]
        out.append(alerta(menu, 'r', 'vigvenc', 'Em execução com a vigência vencida', 'Verificar se houve atraso no repasse (prorrogação de ofício) ou cobrar a prestação de contas; registrar no Transferegov.',
                          [I(r, f'venceu há {-dias(r)} dia(s)') for r in sorted(v_venc, key=dias)]))
        out.append(alerta(menu, 'r', 'vig30', 'Vigência vence em até 30 dias', 'Avaliar a execução: se o objeto não termina no prazo, o convenente deve pedir a prorrogação; se o atraso for do repasse, prorrogar de ofício.',
                          [I(r, f'vence em {dias(r)} dia(s)') for r in sorted(v30, key=dias)]))
        out.append(alerta(menu, 'y', 'vig90', 'Vigência vence em 31 a 90 dias', 'Acompanhar a execução física e financeira e alertar o convenente sobre o prazo.',
                          [I(r, f'vence em {dias(r)} dia(s)') for r in sorted(v90, key=dias)]))
        pcs = [r for r in L if re.search(r'Aguardando Presta', r['situacao'], re.I)]
        pc_v = [r for r in pcs if data(r['limite_prestacao_contas']) and data(r['limite_prestacao_contas']) < HOJE]
        pc_30 = [r for r in pcs if data(r['limite_prestacao_contas']) and 0 <= (data(r['limite_prestacao_contas']) - HOJE).days <= 30]
        out.append(alerta(menu, 'r', 'pcvenc', 'Prestação de contas não enviada no prazo', 'Notificar o convenente; sem resposta, registrar a inadimplência e instaurar a Tomada de Contas Especial.',
                          [I(r, 'prazo foi ' + r['limite_prestacao_contas']) for r in pc_v]))
        out.append(alerta(menu, 'y', 'pc30', 'Prestação de contas vence em até 30 dias', 'Lembrar o convenente do prazo e dos documentos exigidos.',
                          [I(r, 'prazo ' + r['limite_prestacao_contas']) for r in pc_30]))
        cs = [r for r in exe if data(r['clausula_suspensiva_ate']) and (data(r['clausula_suspensiva_ate']) - HOJE).days <= 60]
        out.append(alerta(menu, 'r', 'susp', 'Cláusula suspensiva vence em até 60 dias (ou já venceu)', 'Cobrar os documentos pendentes (projeto, licença, titularidade); vencida sem solução, o instrumento deve ser extinto.',
                          [I(r, 'suspensiva até ' + r['clausula_suspensiva_ate']) for r in cs]))
        sd = [r for r in exe if f(r['valor_a_desembolsar']) > 0 and str(r.get('dias_sem_desembolso') or '').isdigit() and int(r['dias_sem_desembolso']) > 90]
        out.append(alerta(menu, 'y', 'semdes', 'Sem desembolso há mais de 90 dias', 'Verificar com o convenente a licitação e a execução; pedir o cronograma atualizado.',
                          [I(r, f"{r['dias_sem_desembolso']} dias sem desembolso") for r in sorted(sd, key=lambda r: -int(r['dias_sem_desembolso']))]))
        aj = [r for r in L if (r.get('ajuste_pt_aberto') or '').strip()]
        out.append(alerta(menu, 'y', 'ajuste', 'Ajuste do plano de trabalho em aberto', 'Analisar a solicitação no Transferegov dentro do prazo.',
                          [I(r, r['ajuste_pt_aberto']) for r in aj]))
        ob = [(r, obras[r['nr_instrumento']]) for r in exe if r['nr_instrumento'] in obras and str(obras[r['nr_instrumento']].get('dias_sem_medicao') or '').isdigit()
              and int(obras[r['nr_instrumento']]['dias_sem_medicao']) > 90 and not re.search(r'conclu|finaliz', obras[r['nr_instrumento']].get('situacao_obra') or '', re.I)]
        out.append(alerta(menu, 'y', 'obra', 'Obra sem medição há mais de 90 dias', 'Pedir o boletim de medição e verificar se a obra está paralisada (Obrasgov).',
                          [I(r, f"{o['dias_sem_medicao']} dias · {o.get('situacao_obra','')}") for r, o in ob]))
        ina = [r for r in L if (r.get('inadimplente_desde') or '').strip()]
        out.append(alerta(menu, 'r', 'inad', 'Convenente inadimplente', 'Conferir a causa e o prazo para regularização; não liberar recursos até a regularização.',
                          [I(r, 'desde ' + r['inadimplente_desde']) for r in ina]))
        par = [r for r in exe if f(r['saldo_em_conta']) > 0 and str(r.get('dias_sem_desembolso') or '').isdigit() and int(r['dias_sem_desembolso']) > 365]
        out.append(alerta(menu, 'b', 'saldo', 'Saldo em conta parado há mais de 1 ano', 'Cobrar a aplicação do recurso no objeto ou a devolução do saldo.',
                          [I(r, f"saldo R$ {f(r['saldo_em_conta']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')) for r in par]))
        pa = [r for r in inst if filtro(r) and re.search(r'Presta.*(enviada para An|em An|Comprovada em An)', r.get('situacao') or '', re.I)]
        out.append(alerta(menu, 'b', 'pcanal', 'Prestação de contas em análise', 'Analisar e emitir o parecer dentro do prazo do regulamento; priorizar as mais antigas (prazo de envio mais antigo).',
                          [I(r, r['situacao']) for r in sorted(pa, key=lambda r: data(r['limite_prestacao_contas']) or HOJE)]))
        tce = [r for r in L if (r.get('em_processo_tce') or '').upper().startswith('SIM')]
        out.append(alerta(menu, 'b', 'tce', 'Em Tomada de Contas Especial', 'Acompanhar o processo de TCE.', [I(r, 'TCE') for r in tce]))
        for a in out[n0:]:
            a['cols'] = COL_INST
    # Propostas SDR (ano corrente)
    props = ler(os.path.join(saida, 'propostas.csv.gz')) or ler(os.path.join(saida, 'propostas.csv'))
    pa = [p for p in props if p.get('ano_proposta') == str(HOJE.year)]
    # UG da proposta: a do instrumento; sem instrumento, a UG que mais celebra pelo mesmo programa
    from collections import Counter
    ugp = {}
    for x in props + inst:
        if x.get('ug_emitente') and x.get('cod_programa'):
            ugp.setdefault(x['cod_programa'], Counter())[x['ug_emitente']] += 1
    ug_prog = lambda p: p.get('ug_emitente') or (ugp[p['cod_programa']].most_common(1)[0][0] + ' (pelo programa)' if p.get('cod_programa') in ugp else '')
    P = lambda p, info: {'num': p.get('nr_proposta', ''), 'link': p.get('link_proposta', ''), 'ano': p.get('ano_proposta', ''), 'ug': ug_prog(p), 'modalidade': p.get('modalidade', ''),
                         'proponente': p.get('proponente', ''), 'cnpj': p.get('cnpj_proponente', ''), 'uf': p.get('uf', ''), 'municipio': p.get('municipio', ''),
                         'acao': (p.get('acao_orcamentaria') or '')[-4:], 'programa': p.get('programa', ''), 'emenda': p.get('nr_emenda', ''), 'parlamentar': p.get('parlamentar', ''),
                         'objeto': (p.get('objeto') or '')[:300], 'situacao': p.get('situacao_proposta', ''), 'info': info,
                         'valor': round(f(p.get('valor_repasse_proposta')), 2), 'global': round(f(p.get('valor_global_proposta')), 2)}
    comp = [p for p in pa if re.search(r'Complementa', p.get('situacao_proposta') or '', re.I) and not re.search(r'Complementad', p.get('situacao_proposta') or '', re.I)]
    anal = [p for p in pa if re.search(r'Complementad|Enviad[ao] para An|em An[aá]lise', p.get('situacao_proposta') or '', re.I)]
    out.append(alerta('prop', 'y', 'complem', 'Propostas em complementação (com o proponente)', 'Cobrar a complementação do proponente dentro do prazo do programa.', [P(p, 'com o proponente para complementar') for p in comp], cols=COL_PROP))
    out.append(alerta('prop', 'y', 'analise', 'Propostas aguardando análise da área técnica', 'Analisar e emitir parecer; observar o prazo de impedimento técnico das emendas.', [P(p, 'na fila de análise da área técnica') for p in anal], cols=COL_PROP))
    # Captação de Emendas (SIOP)
    try:
        em = json.load(open(os.path.join(saida, 'emendas_siop.json'), encoding='utf-8'))
        sem = [b for b in em.get('linhas', []) if b.get('ano') == str(HOJE.year) and not b.get('proposta') and b.get('modalidade') != 'Aplicação direta']
        out.append(alerta('captacao', 'y', 'semprop', 'Emenda indicada sem proposta no Transferegov', 'Contatar o beneficiário para cadastrar a proposta ou avaliar o impedimento técnico.',
                          [{'num': b['emenda'], 'ano': b.get('ano', ''), 'autor': b.get('autor', ''), 'partido': b.get('partido', ''), 'acao': b.get('acao', ''),
                            'ug': b.get('ug') or {'20ZY': '130010', '8622': '420013', '215A': '420013', '8593': '420013', '214Z': '420013', '21B6': '420013', '8606': '420013'}.get(b.get('acao'), ''),
                            'area': b.get('area', ''), 'entidade': b.get('entidade', ''), 'cnpj': b.get('cnpj', ''), 'uf': b.get('uf', ''), 'modalidade': b.get('modalidade', ''),
                            'tipo': b.get('tipo_despesa', ''), 'info': 'sem proposta cadastrada', 'indicado': b.get('indicado', 0)} for b in sem], cols=COL_EMENDA))
    except Exception:
        pass
    return out


def ted(saida):
    T = ler(os.path.join(saida, 'ted', 'ted_base_atualizada.csv'))
    try:
        ptF = {k: v['ptF'] for k, v in json.load(open(os.path.join(saida, 'ted', 'ted_ficha.json'), encoding='utf-8')).items() if v.get('ptF')}
    except Exception:
        ptF = {}
    out = []
    EQ = {'130010', '420013'}
    for menu, filtro in (('ted', lambda r: r['UG descentralizadora'] in EQ or r['UG descentralizada'] in EQ),
                         ('tedapi', lambda r: not (r['UG descentralizadora'] in EQ or r['UG descentralizada'] in EQ))):
        L = [r for r in T if filtro(r)]
        exe = [r for r in L if r.get('Fase (painel)') == 'Em execução']
        d = lambda r: int(r['Dias para o fim']) if re.match(r'^-?\d+$', r.get('Dias para o fim') or '') else None
        I = lambda r, info: {'num': r['Nº TED'] or r.get('Plano de ação'), 'ano': r.get('Ano', ''), 'plano': r.get('Plano de ação', ''), 'sentido': r.get('Enviado / recebido', ''),
                             'ugdor': r.get('UG descentralizadora', ''), 'ugda': r.get('UG descentralizada', ''), 'unid': r.get('Unidade descentralizada', ''), 'processo': r.get('Processo', ''),
                             'acao': r.get('Ação', ''), 'objeto': (r.get('Objeto') or '')[:300], 'situacao': r.get('Situação do termo (API)') or r.get('Situação no Tesouro', ''),
                             'fim': r.get('Fim da vigência (painel)', ''), 'dias': d(r), 'nc_lista': (r.get('Notas de crédito') or '')[:300], 'info': info,
                             'firmado': round(f(r.get('Valor firmado (API)')) or f(r.get('Valor firmado (Tesouro)')), 2), 'nc': round(f(r.get('Descentralizado NC (API)')) or f(r.get('NC no Tesouro')), 2),
                             'repassado': round(f(r.get('Repassado PF (API)')) or f(r.get('Repassado (Tesouro)')), 2), 'empenhado': round(f(r.get('Empenhado pela unidade (NE)')), 2),
                             'pago': round(f(r.get('Pago pela unidade (NE + RP)')), 2), 'acomprovar': round(f(r.get('A comprovar (Tesouro)')), 2)}
        vv = [r for r in exe if d(r) is not None and d(r) < 0]
        v30 = [r for r in exe if d(r) is not None and 0 <= d(r) <= 30]
        v90 = [r for r in exe if d(r) is not None and 30 < d(r) <= 90]
        out.append(alerta(menu, 'r', 'vigvenc', 'Em execução com a vigência vencida', 'Conferir se houve prorrogação não registrada; se não, cobrar o relatório de cumprimento do objeto (Decreto 10.426/2020).', [I(r, f'venceu há {-d(r)} dia(s)') for r in vv]))
        out.append(alerta(menu, 'r', 'vig30', 'Vigência vence em até 30 dias', 'Avaliar com a unidade descentralizada a prorrogação ou o encerramento.', [I(r, f'vence em {d(r)} dia(s)') for r in v30]))
        out.append(alerta(menu, 'y', 'vig90', 'Vigência vence em 31 a 90 dias', 'Acompanhar a execução e o prazo.', [I(r, f'vence em {d(r)} dia(s)') for r in v90]))
        semnc = [r for r in exe if f(r.get('Descentralizado NC (API)')) == 0 and f(r.get('NC no Tesouro')) == 0 and r.get('Enviado / recebido') == 'Enviado']
        out.append(alerta(menu, 'r', 'semnc', 'TED em execução sem crédito descentralizado (sem NC)', 'Emitir a nota de crédito ou conferir no Tesouro se a NC foi emitida e ainda não aparece no relatório.', [I(r, 'sem NC') for r in semnc]))
        kT = lambda r: re.sub(r'[^0-9A-Z]', '', (r.get('Nº TED') or '').upper().split(' ')[0]).lstrip('0')
        fora = [r for r in exe if ptF.get(kT(r))]
        out.append(alerta(menu, 'r', 'ptresne', 'PTRES fora do relatório "EMPENHOS TED" (Tesouro Gerencial)', 'Incluir o PTRES no filtro do relatório EMPENHOS TED no Tesouro Gerencial e rodar o robô: sem isso o painel não mostra os empenhos da unidade e o TED pode aparecer como "sem empenho".',
                          [I(r, 'PTRES ' + ', '.join(ptF[kT(r)]) + ' fora do relatório') for r in fora]))
        ncsemne = [r for r in exe if not ptF.get(kT(r)) and (f(r.get('Descentralizado NC (API)')) > 0 or f(r.get('NC no Tesouro')) > 0) and f(r.get('Empenhado pela unidade (NE)')) == 0 and r.get('Enviado / recebido') == 'Enviado']
        out.append(alerta(menu, 'y', 'ncsemne', 'Crédito descentralizado sem empenho pela unidade', 'Cobrar da unidade descentralizada o empenho do crédito recebido.', [I(r, 'NC sem empenho') for r in ncsemne]))
        comp = [r for r in L if f(r.get('A comprovar (Tesouro)')) > 0 and d(r) is not None and d(r) < -60]
        out.append(alerta(menu, 'y', 'comprovar', 'Saldo a comprovar com a vigência encerrada há mais de 60 dias', 'Cobrar o relatório de cumprimento do objeto e a comprovação no SIAFI.', [I(r, 'a comprovar no Tesouro') for r in comp]))
        # (04/11/2026) saiu o alerta "Diferença entre a API do TED e o Tesouro": os valores do TED vêm só do Tesouro e da planilha de controle
    for a in out:
        a['cols'] = COL_TED
    return out


# ---------- departamento, controle, prazo e prioridade de cada item ----------
# departamento pela UG (130141 e 135098 = CGPI · 130255 = PROMAQ · 130010 = CEPLAC); na 420013, pela ação
DEP_UG = {'130141': 'CGPI', '135098': 'CGPI', '130255': 'PROMAQ', '130010': 'CEPLAC'}
DEP_ACAO = {'8593': 'DEPROS', '214Z': 'DIAGRO', '00PN': 'DIAGRO', '215A': 'DECAP', '8622': 'DECAP', '21B6': 'DECAP', '8606': 'DECAP', '20ZY': 'CEPLAC', '2000': 'SDR'}
UGS_SDR = ('130010', '130141', '130255', '135098', '420013')
EQUIPE = {'130010', '420013'}   # o que a equipe controla (TED EQUIPE SDR, Convênio/TF 420013, contratos da CEPLAC)


def departamento(ug, acao):
    ug, acao = str(ug or '')[:6], str(acao or '').strip()[-4:].upper()
    if acao == '20ZY':
        return 'CEPLAC'
    if ug == '420013':
        return DEP_ACAO.get(acao, 'SDR')
    return DEP_UG.get(ug) or DEP_ACAO.get(acao) or 'SDR'


def dias_ate(s):
    d = data(s)
    return (d - HOJE).days if d else None


def prioridade(sev, valor, dias):
    """0 a 99: gravidade + valor (R$ 10 mil = 0 … R$ 10 milhões = 25) + prazo (vencido ou até 30 dias pesa mais)."""
    import math
    p = {'r': 55, 'y': 35, 'b': 15}.get(sev, 15)
    if valor and valor > 0:
        p += min(25, max(0, (math.log10(valor) - 4) * 8.3))
    if dias is not None:
        p += min(19, 8 + (-dias) / 30) if dias < 0 else 15 if dias <= 30 else 8 if dias <= 90 else 0
    return int(min(99, round(p)))


def faixa_dias(n, cortes):
    for lim, rot in cortes:
        if n <= lim:
            return rot
    return cortes[-1][1]


def enriquecer(lista):
    for a in lista:
        for it in a['itens']:
            if a['menu'] in ('ted', 'tedapi'):
                ug = it.get('ugdor') if str(it.get('ugdor') or '')[:6] in UGS_SDR and it.get('sentido') != 'Recebido' else it.get('ugda') or it.get('ugdor')
                valor = max(it.get('firmado') or 0, it.get('nc') or 0, it.get('acomprovar') or 0)
            else:
                ug = it.get('ug') or ''
                valor = it.get('repasse') or it.get('valor') or it.get('indicado') or 0
            ug = re.sub(r'\D', '', str(ug))[:6]
            it['dep'] = it.get('area') if a['menu'] == 'captacao' and it.get('area') else departamento(ug, it.get('acao'))
            it['ctrl'] = 'Equipe SDR' if ug in EQUIPE or a['menu'] in ('ted', 'conv') else 'Geral SDR'
            dias = None
            if a['id'] in ('vigvenc', 'vig30', 'vig90'):
                dias = it.get('dias') if isinstance(it.get('dias'), int) else dias_ate(it.get('fim'))
            elif a['id'] in ('pcvenc', 'pc30'):
                dias = dias_ate(it.get('prazo_pc'))
            elif a['id'] == 'susp':
                m = re.search(r'(\d{2}/\d{2}/\d{4})', it.get('info') or '')
                dias = dias_ate(m[1]) if m else None
            elif a['id'] == 'comprovar':
                dias = it.get('dias') if isinstance(it.get('dias'), int) else None
            it['prazo_d'] = dias
            it['prior'] = prioridade(a['sev'], valor, dias)
            it['vprior'] = round(valor or 0, 2)
            # faixas de tempo para as listas grandes
            if a['id'] in ('semdes', 'saldo'):
                m = re.match(r'(\d+)', str(it.get('info') or ''))
                n = int(m[1]) if m else None
                if a['id'] == 'semdes' and n is not None:
                    it['faixa'] = faixa_dias(n, [(180, '90 a 180 dias'), (365, '180 dias a 1 ano'), (10 ** 9, 'mais de 1 ano')])
            if a['id'] == 'pcanal':
                d = dias_ate(it.get('prazo_pc'))
                n = -d if d is not None else None
                it['faixa'] = 'sem data' if n is None else faixa_dias(n, [(365, 'até 1 ano'), (730, '1 a 2 anos'), (10 ** 9, 'mais de 2 anos')])
        a['itens'].sort(key=lambda x: -x.get('prior', 0))
    return lista


def main(saida):
    out = {'gerado_em': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M'), 'hoje': HOJE.strftime('%d/%m/%Y'),
           'parc': enriquecer(parcerias(saida)), 'ted': enriquecer(ted(saida))}
    json.dump(out, open(os.path.join(saida, 'alertas.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    for k in ('parc', 'ted'):
        print(k, ' · '.join(f"{a['menu']}/{a['id']}={len(a['itens'])}" for a in out[k] if a['itens']), flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
