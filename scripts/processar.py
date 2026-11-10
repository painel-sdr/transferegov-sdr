"""
Robô Transferegov · SDR/MAPA
Baixa os arquivos de dados abertos do Transferegov (Discricionárias e Legais), filtra o que é da SDR
e gera arquivos CSV pequenos e organizados, prontos para o Painel SDR e para as planilhas.

Escopo SDR:
  • instrumentos (convênios, contratos de repasse, termos de fomento/colaboração) emitidos pelas UGs da SDR;
  • propostas desses instrumentos + todas as propostas dos mesmos programas (inclusive as não celebradas).

Uso:  python scripts/processar.py PASTA_DE_SAIDA
      (variável FONTE_LOCAL=pasta com os .zip já baixados, para testar sem internet)
"""
import csv, gzip, io, json, os, sys, time, urllib.request, zipfile, datetime, re

BASE = 'https://api-publica.transferegov.gestao.gov.br/downloads/dadosgov/'
ORGAO_MAPA = '22000'
UGS_SDR = ['130010', '130141', '135098', '420013', '130255']
# ações da SDR: programa do Transferegov com uma delas entra no escopo de propostas (a 2000 fica de fora: é usada por outras secretarias do MAPA)
ACOES_SDR = {'20ZV', '8593', '214Z', '00PN', '215A', '8622', '21B6', '8606', '20ZY'}
ARQUIVOS = ['siconv_convenio', 'siconv_programa_proposta', 'siconv_programa', 'siconv_proposta', 'siconv_emenda',
            'siconv_empenho', 'siconv_desembolso', 'siconv_termo_aditivo', 'siconv_prorroga_oficio', 'data_carga_siconv',
            'siconv_dados_obrasgov_geral', 'siconv_acomp_obras_contratos_medicoes_modulo_empresas', 'siconv_acomp_obras_valores_itens_medicao_modulo_empresas', 'siconv_resumo_fisico_financeiro', 'siconv_historico_situacao', 'siconv_pagamento', 'siconv_cronograma_desembolso', 'siconv_solicitacao_ajuste_pt',
            'siconv_plano_aplicacao_detalhado', 'siconv_meta_crono_fisico', 'siconv_etapa_crono_fisico',
            'siconv_licitacao', 'siconv_contrato',
            'siconv_empenho_desembolso']   # qual empenho pagou cada desembolso (se o arquivo não vier, a coluna fica em branco)   # execução do convenente (processos de execução e contratos)
TMP = os.environ.get('FONTE_LOCAL') or '/tmp/transferegov'
csv.field_size_limit(10**9)
LOG = []


def log(msg):
    linha = time.strftime('%H:%M:%S') + '  ' + msg
    print(linha, flush=True)
    LOG.append(linha)
    if os.environ.get('GITHUB_ACTIONS'):
        print('::notice::' + msg, flush=True)


# ---------------------------------------------------------------- download
def baixar(nome):
    destino = os.path.join(TMP, nome + '.zip')
    if os.environ.get('FONTE_LOCAL'):
        return destino if os.path.exists(destino) else None
    os.makedirs(TMP, exist_ok=True)
    for tentativa in range(1, 4):
        try:
            t = time.time()
            req = urllib.request.Request(BASE + nome + '.zip', headers={'User-Agent': 'robo-sdr-mapa'})
            with urllib.request.urlopen(req, timeout=600) as r, open(destino, 'wb') as f:
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
            log(f'baixou {nome}.zip · {os.path.getsize(destino)/1048576:.1f} MB · {time.time()-t:.1f} s')
            return destino
        except Exception as e:
            log(f'falha ao baixar {nome} (tentativa {tentativa}): {e}')
            time.sleep(10 * tentativa)
    return None


def linhas(nome):
    """Lê o CSV de dentro do .zip linha a linha (sem carregar tudo na memória). Devolve (cabeçalho, iterador de dicts)."""
    caminho = os.path.join(TMP, nome + '.zip')
    if not os.path.exists(caminho):
        return None, iter(())
    z = zipfile.ZipFile(caminho)
    membro = next((n for n in z.namelist() if n.lower().endswith('.csv')), z.namelist()[0])
    bruto = io.TextIOWrapper(z.open(membro), encoding='utf-8-sig', newline='')
    leitor = csv.reader(bruto, delimiter=';')
    cab = [c.strip().upper() for c in next(leitor)]

    def gerar():
        for r in leitor:
            if len(r) < len(cab):
                r = r + [''] * (len(cab) - len(r))
            yield dict(zip(cab, r))
    return cab, gerar()


# ---------------------------------------------------------------- formatos
def num(s):
    """'1869731,8' · '242754.81' · '1.234,56' · '' → float"""
    s = (s or '').strip()
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def data(s):
    s = (s or '').strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.datetime.strptime(s[:19], fmt).date()
        except ValueError:
            pass
    return None


def br(d):
    return d.strftime('%d/%m/%Y') if d else ''


def v2(x):
    return f'{x:.2f}'


def gravar(pasta, nome, campos, registros):
    caminho = os.path.join(pasta, nome)
    with open(caminho, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        w.writeheader()
        for r in registros:
            w.writerow(r)
    log(f'gravou {nome} · {len(registros)} linhas · {os.path.getsize(caminho)/1048576:.1f} MB')


# ---------------------------------------------------------------- principal
def main(saida):
    os.makedirs(saida, exist_ok=True)
    hoje = datetime.date.today()
    meta = {'gerado_em': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M'),
            'ugs': UGS_SDR, 'cabecalhos': {}, 'contagens': {}}

    for a in ARQUIVOS:
        baixar(a)

    # data da carga do Transferegov
    cab, it = linhas('data_carga_siconv')
    for r in it:
        meta['data_carga'] = ' '.join(v for v in r.values() if v)
        break

    # 1. instrumentos das UGs da SDR
    cab, it = linhas('siconv_convenio')
    meta['cabecalhos']['convenio'] = cab
    conv = {}
    for r in it:
        if r.get('UG_EMITENTE') in UGS_SDR:
            conv[r['NR_CONVENIO']] = r
    prop_do_conv = {r['ID_PROPOSTA']: n for n, r in conv.items()}
    log(f'instrumentos da SDR: {len(conv)}')

    # 2. programas usados pela SDR → escopo de propostas
    #    (a) programas do MAPA cuja ação orçamentária é da SDR (pega programa novo, ainda sem nenhum instrumento celebrado)
    #    (b) programas que já têm instrumento de uma UG da SDR (regra antiga)
    cab, it = linhas('siconv_programa')
    progs_acao = set()
    for r in it:
        if (r.get('COD_ORGAO_SUP_PROGRAMA') or '').strip() == ORGAO_MAPA:
            acoes = set(re.findall(r'\b[0-9A-Z]{4}\b', (r.get('ACAO_ORCAMENTARIA') or '').upper()))
            if acoes & ACOES_SDR:
                progs_acao.add(r.get('ID_PROGRAMA'))
    log(f'programas do MAPA com ação da SDR ({", ".join(sorted(ACOES_SDR))}): {len(progs_acao)}')
    cab, it = linhas('siconv_programa_proposta')
    meta['cabecalhos']['programa_proposta'] = cab
    progs_da_prop, pares = {}, []
    for r in it:
        pares.append((r.get('ID_PROPOSTA'), r.get('ID_PROGRAMA')))
    for p, g in pares:
        if p in prop_do_conv:
            progs_da_prop.setdefault(p, set()).add(g)
    progs_sdr = set(g for gs in progs_da_prop.values() for g in gs)
    progs_sdr |= progs_acao
    escopo = set(prop_do_conv)
    for p, g in pares:
        if g in progs_sdr:
            escopo.add(p)
            progs_da_prop.setdefault(p, set()).add(g)
    pares = None
    log(f'programas da SDR: {len(progs_sdr)} · propostas no escopo: {len(escopo)}')

    cab, it = linhas('siconv_programa')
    meta['cabecalhos']['programa'] = cab
    programa = {r['ID_PROGRAMA']: r for r in it if r.get('ID_PROGRAMA') in progs_sdr}

    # 3. propostas (arquivo grande, lido em fluxo)
    cab, it = linhas('siconv_proposta')
    meta['cabecalhos']['proposta'] = cab
    proposta = {}
    for r in it:
        if r.get('ID_PROPOSTA') in escopo and (r.get('COD_ORGAO') or '').strip() == ORGAO_MAPA:
            proposta[r['ID_PROPOSTA']] = r
    log(f'propostas lidas (só concedente {ORGAO_MAPA}): {len(proposta)}')
    # só instrumentos cujo concedente é o Ministério da Agricultura e Pecuária (a UG emitente sozinha deixa passar outros ministérios)
    fora = [n for n, c in conv.items() if c.get('ID_PROPOSTA') not in proposta]
    for n in fora:
        del conv[n]
    escopo = set(proposta)
    gravar(saida, 'instrumentos_outros_orgaos.csv', ['nr_instrumento', 'ug_emitente', 'id_proposta'], [{'nr_instrumento': n, 'ug_emitente': '', 'id_proposta': ''} for n in fora])
    log(f'instrumentos de outros órgãos retirados: {len(fora)} ({", ".join(fora[:20])}) · ficam {len(conv)}')

    # 4. emendas
    cab, it = linhas('siconv_emenda')
    meta['cabecalhos']['emenda'] = cab
    emendas = [r for r in it if r.get('ID_PROPOSTA') in escopo]
    emendas_da_prop = {}
    for r in emendas:
        emendas_da_prop.setdefault(r['ID_PROPOSTA'], []).append(r)

    # 5. empenhos, desembolsos, aditivos e prorrogações dos instrumentos
    def do_conv(nome):
        cab, it = linhas(nome)
        meta['cabecalhos'][nome.replace('siconv_', '')] = cab
        if cab and 'NR_CONVENIO' not in cab and 'ID_PROPOSTA' in cab:   # arquivos ligados pela proposta (ex.: cronograma)
            props = {c.get('ID_PROPOSTA') for c in conv.values()}
            out = [r for r in it if r.get('ID_PROPOSTA') in props]
        else:
            out = [r for r in it if r.get('NR_CONVENIO') in conv]
        log(f'{nome}: {len(out)} linhas da SDR')
        return cab, out
    cab_emp, empenhos = do_conv('siconv_empenho')
    cab_des, desembolsos = do_conv('siconv_desembolso')
    cab_ta, aditivos = do_conv('siconv_termo_aditivo')
    cab_pr, prorrogas = do_conv('siconv_prorroga_oficio')
    cab_hs, historico = do_conv('siconv_historico_situacao')
    cab_pg, pagamentos = do_conv('siconv_pagamento')
    cab_cr, cronograma = do_conv('siconv_cronograma_desembolso')
    cab_aj, ajustes_pt = do_conv('siconv_solicitacao_ajuste_pt')
    # plano de trabalho: PAD (itens) e cronograma físico (metas e etapas) · para o relatório do instrumento
    cab_pad, pad = do_conv('siconv_plano_aplicacao_detalhado')
    cab_mt, metas = do_conv('siconv_meta_crono_fisico')
    cab_et, it_et = linhas('siconv_etapa_crono_fisico')
    meta['cabecalhos']['etapa_crono_fisico'] = cab_et
    ids_meta = {m.get('ID_META') for m in metas if m.get('ID_META')}
    etapas = [r for r in it_et if r.get('ID_META') in ids_meta] if cab_et and 'ID_META' in cab_et else \
             [r for r in it_et if r.get('NR_CONVENIO') in conv] if cab_et and 'NR_CONVENIO' in cab_et else []
    log(f'siconv_etapa_crono_fisico: {len(etapas)} linhas da SDR')
    # execução do convenente: processos de execução (licitações) e contratos/subconvênios registrados no Transferegov
    cab_lic, licitacoes = do_conv('siconv_licitacao')
    cab_ctc, it_ctc = linhas('siconv_contrato')
    meta['cabecalhos']['contrato'] = cab_ctc
    ids_lic = {r.get('ID_LICITACAO') for r in licitacoes if r.get('ID_LICITACAO')}
    props_sdr = {c.get('ID_PROPOSTA') for c in conv.values()}
    if cab_ctc and 'NR_CONVENIO' in cab_ctc:
        contratos_conv = [r for r in it_ctc if r.get('NR_CONVENIO') in conv]
    elif cab_ctc and 'ID_PROPOSTA' in cab_ctc:
        contratos_conv = [r for r in it_ctc if r.get('ID_PROPOSTA') in props_sdr]
    elif cab_ctc and 'ID_LICITACAO' in cab_ctc:
        contratos_conv = [r for r in it_ctc if r.get('ID_LICITACAO') in ids_lic]
    else:
        contratos_conv = []
    log(f'siconv_contrato: {len(contratos_conv)} linhas da SDR · colunas: {",".join(cab_ctc or [])}')
    log(f'siconv_licitacao: colunas: {",".join(cab_lic or [])}')
    # histórico: primeira vez que o instrumento ficou INADIMPLENTE e a sequência de situações
    inad_c, hist_c = {}, {}
    for h in historico:
        n, s, d = h['NR_CONVENIO'], (h.get('HISTORICO_SIT') or '').strip(), data(h.get('DIA_HISTORICO_SIT'))
        hist_c.setdefault(n, []).append((d or datetime.date.min, s))
        if 'INADIMPL' in s.upper() and d and (n not in inad_c or d < inad_c[n]):
            inad_c[n] = d

    def por_conv(lista):
        g = {}
        for r in lista:
            g.setdefault(r['NR_CONVENIO'], []).append(r)
        return g
    emp_c, des_c, ta_c, pr_c = por_conv(empenhos), por_conv(desembolsos), por_conv(aditivos), por_conv(prorrogas)

    def info_prop(p):
        pr = proposta.get(p, {})
        gs = sorted(progs_da_prop.get(p, []))
        pg = [programa[g] for g in gs if g in programa]
        em = emendas_da_prop.get(p, [])
        return {
            'id_proposta': p,
            'nr_proposta': pr.get('NR_PROPOSTA', ''),
            'ano_proposta': pr.get('ANO_PROP', ''),
            'situacao_proposta': pr.get('SIT_PROPOSTA', ''),
            'modalidade': pr.get('MODALIDADE', ''),
            'orgao_concedente': (pr.get('COD_ORGAO', '') + ' - ' + pr.get('DESC_ORGAO', '')).strip(' -'),
            'cnpj_proponente': pr.get('IDENTIF_PROPONENTE', ''),
            'proponente': pr.get('NM_PROPONENTE', ''),
            'natureza_juridica': pr.get('NATUREZA_JURIDICA', ''),
            'uf': pr.get('UF_PROPONENTE', ''),
            'municipio': pr.get('MUNIC_PROPONENTE', ''),
            'cod_ibge': pr.get('COD_MUNIC_IBGE', ''),
            'objeto': (pr.get('OBJETO_PROPOSTA', '') or '').replace('\r', ' ').replace('\n', ' ').strip(),
            'valor_global_proposta': v2(num(pr.get('VL_GLOBAL_PROP'))),
            'valor_repasse_proposta': v2(num(pr.get('VL_REPASSE_PROP'))),
            'valor_contrapartida_proposta': v2(num(pr.get('VL_CONTRAPARTIDA_PROP'))),
            'inicio_vigencia_proposta': pr.get('DIA_INIC_VIGENCIA_PROPOSTA', ''),
            'fim_vigencia_proposta': pr.get('DIA_FIM_VIGENCIA_PROPOSTA', ''),
            'cod_programa': ' | '.join(x.get('COD_PROGRAMA', '') for x in pg),
            'programa': ' | '.join(x.get('NOME_PROGRAMA', '') for x in pg),
            'acao_orcamentaria': ' | '.join(sorted(set(x.get('ACAO_ORCAMENTARIA', '') for x in pg if x.get('ACAO_ORCAMENTARIA')))),
            'id_programa': ' | '.join(gs),
            'nr_emenda': ' | '.join(sorted(set(e.get('NR_EMENDA', '') for e in em if e.get('NR_EMENDA')))),
            'parlamentar': ' | '.join(sorted(set(e.get('NOME_PARLAMENTAR', '') for e in em if e.get('NOME_PARLAMENTAR')))),
            'tipo_parlamentar': ' | '.join(sorted(set(e.get('TIPO_PARLAMENTAR', '') for e in em if e.get('TIPO_PARLAMENTAR')))),
            'valor_emenda': v2(sum(num(e.get('VALOR_REPASSE_EMENDA')) for e in em)),
            'link_proposta': 'https://discricionarias.transferegov.sistema.gov.br/voluntarias/ConsultarProposta/ResultadoDaConsultaDePropostaDetalharProposta.do?idProposta=' + p + '&Usr=guest&Pwd=guest',
        }

    # 6. instrumentos (1 linha por instrumento)
    inst = []
    for n, c in conv.items():
        rep, desemb = num(c.get('VL_REPASSE_CONV')), num(c.get('VL_DESEMBOLSADO_CONV'))
        ds = sorted((data(d.get('DATA_DESEMBOLSO')) for d in des_c.get(n, [])), key=lambda x: x or datetime.date.min)
        ult = ds[-1] if ds and ds[-1] else None
        emps = emp_c.get(n, [])
        nes = sorted(set(e.get('NR_EMPENHO', '') for e in emps if e.get('NR_EMPENHO')))
        reg = {
            'nr_instrumento': n,
            'ug_emitente': c.get('UG_EMITENTE', ''),
            'situacao': c.get('SIT_CONVENIO', ''),
            'subsituacao': c.get('SUBSITUACAO_CONV', ''),
            'instrumento_ativo': c.get('INSTRUMENTO_ATIVO', ''),
            'assinado': c.get('IND_ASSINADO', ''),
            'ano': c.get('ANO', ''),
            'nr_processo': c.get('NR_PROCESSO', ''),
            'data_assinatura': c.get('DIA_ASSIN_CONV', ''),
            'data_publicacao': c.get('DIA_PUBL_CONV', ''),
            'inicio_vigencia': c.get('DIA_INIC_VIGENC_CONV', ''),
            'fim_vigencia': c.get('DIA_FIM_VIGENC_CONV', ''),
            'fim_vigencia_original': c.get('DIA_FIM_VIGENC_ORIGINAL_CONV', ''),
            'limite_prestacao_contas': c.get('DIA_LIMITE_PREST_CONTAS', ''),
            'clausula_suspensiva_ate': c.get('DATA_SUSPENSIVA', ''),
            'situacao_contratacao': c.get('SITUACAO_CONTRATACAO', ''),
            'valor_global': v2(num(c.get('VL_GLOBAL_CONV'))),
            'valor_global_original': v2(num(c.get('VALOR_GLOBAL_ORIGINAL_CONV'))),
            'valor_repasse': v2(rep),
            'valor_contrapartida': v2(num(c.get('VL_CONTRAPARTIDA_CONV'))),
            'valor_empenhado': v2(num(c.get('VL_EMPENHADO_CONV'))),
            'valor_desembolsado': v2(desemb),
            'valor_a_desembolsar': v2(max(0.0, rep - desemb)),
            'pct_desembolsado': f'{(desemb / rep * 100) if rep else 0:.2f}',
            'ingresso_contrapartida': v2(num(c.get('VL_INGRESSO_CONTRAPARTIDA'))),
            'rendimento_aplicacao': v2(num(c.get('VL_RENDIMENTO_APLICACAO'))),
            'saldo_em_conta': v2(num(c.get('VL_SALDO_CONTA'))),
            'qtd_desembolsos': str(len(ds)),
            'ultimo_desembolso': br(ult),
            'dias_sem_desembolso': str((hoje - ult).days) if ult else '',
            'qtd_aditivos': str(len(ta_c.get(n, []))),
            'qtd_prorrogacoes': str(len(pr_c.get(n, []))),
            'saldo_devolvido_tesouro': v2(num(c.get('VL_SALDO_REMAN_TESOURO'))),
            'saldo_devolvido_convenente': v2(num(c.get('VL_SALDO_REMAN_CONVENENTE'))),
            'em_processo_tce': 'SIM' if 'TCE' in (c.get('SUBSITUACAO_CONV', '') or '').upper() else 'NÃO',
            'inadimplente_desde': br(inad_c.get(n)),
            'ultima_mudanca_situacao': br(max(hist_c[n])[0]) if hist_c.get(n) else '',
            'ugs_empenho': ' | '.join(sorted(set(e.get('UG_EMITENTE', '') for e in emps if e.get('UG_EMITENTE')))),
            'notas_empenho': ' | '.join(nes),
            'qtd_notas_empenho': str(len(nes)),
        }
        reg.update(info_prop(c.get('ID_PROPOSTA', '')))
        inst.append(reg)
    # ação orçamentária que falta (programa sem ação no Transferegov): pela PTRES das notas de empenho
    ptres_acao = {}
    for r in inst:
        acs = [a for a in r['acao_orcamentaria'].split(' | ') if a]
        if len(acs) == 1:
            for e in emp_c.get(r['nr_instrumento'], []):
                pt = (e.get('PTRES') or '').strip()
                if pt:
                    ptres_acao.setdefault(pt, {}).setdefault(acs[0], 0)
                    ptres_acao[pt][acs[0]] += 1
    preench = 0
    for r in inst:
        r['acao_pela_ptres'] = ''
        if r['acao_orcamentaria']:
            continue
        cont = {}
        for e in emp_c.get(r['nr_instrumento'], []):
            for a, q in ptres_acao.get((e.get('PTRES') or '').strip(), {}).items():
                cont[a] = cont.get(a, 0) + q
        if cont:
            r['acao_orcamentaria'] = max(cont, key=cont.get)
            r['acao_pela_ptres'] = 'SIM'
            preench += 1
    log(f'ação orçamentária preenchida pela PTRES das notas: {preench} instrumentos')
    # ajuste de valor: aditivos de valor e solicitações de ajuste do plano de trabalho
    ta_c = por_conv(aditivos)
    aj_c = por_conv([a for a in ajustes_pt if a.get('NR_CONVENIO')]) if ajustes_pt and 'NR_CONVENIO' in (cab_aj or []) else {}
    if ajustes_pt and 'NR_CONVENIO' not in (cab_aj or []) and 'ID_PROPOSTA' in (cab_aj or []):
        for a in ajustes_pt:
            n = prop_do_conv.get(a.get('ID_PROPOSTA'))
            if n:
                aj_c.setdefault(n, []).append(a)
    # Acesso Livre (robô acesso_livre, branch abas): situação atual dos ajustes do PT, que nos dados abertos pode estar dias atrasada
    try:
        import urllib.request
        AL = json.load(urllib.request.urlopen('https://raw.githubusercontent.com/painel-sdr/transferegov-sdr/abas/acesso_livre.json', timeout=60))
    except Exception as e:
        AL = {}
        log(f'acesso livre indisponível: {e}')
    def al_ajustes(n):
        abas = (AL.get(n) or {}).get('abas')
        if not abas:
            return None
        return [dict(zip(x.get('ths', []), row)) for x in abas.get('ajustes', []) for row in x.get('rows', [])]
    for r in inst:
        n = r['nr_instrumento']
        tas = [a for a in ta_c.get(n, []) if num(a.get('VL_REPASSE_TA')) or num(a.get('VL_GLOBAL_TA'))]
        r['aditivos_valor'] = ' | '.join(f"{a.get('NUMERO_TA','')} {a.get('TIPO_TA','')} repasse {v2(num(a.get('VL_REPASSE_TA')))} em {a.get('DT_ASSINATURA_TA','')}".strip() for a in tas)
        r['supressao_repasse_ta'] = v2(sum(num(a.get('VL_REPASSE_TA')) for a in tas if 'SUPRESS' in (a.get('TIPO_TA') or '').upper()))
        ajs = aj_c.get(n, [])
        datas = [x for x in (data(next((a.get(k) for k in a if 'DATA' in k or k.startswith('DT_')), '')) for a in ajs) if x]
        r['qtd_ajustes_pt'] = str(len(ajs))
        r['ultimo_ajuste_pt'] = br(max(datas)) if datas else ''
        # solicitações de ajuste do PT ainda em aberto (não aprovadas nem negadas)
        abertos = sorted({(a.get('SITUACAO_SOLICITACAO_AJUSTE_PT') or '').strip() for a in ajs} - {'', 'Ajustado e Aprovado', 'Não Autorizado'})
        al = al_ajustes(n)
        if al is not None:   # lido hoje no Acesso Livre: vale sobre os dados abertos
            abertos = sorted({(x.get('Situação') or '').strip() for x in al} - {'', 'Ajustado e Aprovado', 'Não Autorizado', 'Cancelado', 'Rejeitado'})
        r['ajuste_pt_aberto'] = ' | '.join(abertos)
        rep_orig = num(r.get('valor_repasse_proposta'))
        r['reducao_repasse'] = v2(max(0.0, rep_orig - num(r['valor_repasse']))) if rep_orig else '0.00'
    inst.sort(key=lambda r: (r['ano'] or '0000', r['nr_instrumento']), reverse=True)
    campos_inst = list(inst[0].keys()) if inst else []
    gravar(saida, 'instrumentos.csv', campos_inst, inst)
    # versão leve para o painel (abre rápido no navegador)
    leve = ['nr_instrumento', 'ug_emitente', 'ano', 'situacao', 'situacao_contratacao', 'clausula_suspensiva_ate', 'fim_vigencia',
            'limite_prestacao_contas', 'nr_processo', 'modalidade', 'proponente', 'uf', 'municipio', 'natureza_juridica', 'tipo_parlamentar',
            'valor_repasse', 'valor_desembolsado', 'valor_a_desembolsar', 'ultimo_desembolso', 'dias_sem_desembolso', 'qtd_aditivos',
            'qtd_prorrogacoes', 'notas_empenho', 'saldo_em_conta', 'subsituacao', 'em_processo_tce', 'inadimplente_desde', 'ugs_empenho', 'acao_orcamentaria', 'cod_programa', 'programa', 'valor_global', 'valor_global_original',
            'valor_repasse_proposta', 'supressao_repasse_ta', 'qtd_ajustes_pt', 'ultimo_ajuste_pt', 'ajuste_pt_aberto', 'reducao_repasse', 'aditivos_valor', 'objeto']
    gravar(saida, 'painel_instrumentos.csv', leve, [{**r, 'objeto': r['objeto'][:160]} for r in inst])
    with open(os.path.join(saida, 'painel_instrumentos.csv'), 'rb') as fi, gzip.open(os.path.join(saida, 'painel_instrumentos.csv.gz'), 'wb', compresslevel=9) as fo:
        fo.write(fi.read())   # o painel baixa a versão comprimida (15 MB → 2,6 MB)

    # 6b. arquivo no formato da planilha "Parcerias" (mesmos nomes e ordem de colunas A:AH), usado pelo Apps Script da planilha
    def faixa(d):
        return 'Até 90 dias' if d <= 90 else 'Acima de 90 até 180 dias' if d <= 180 else 'Acima de 180 até 365 dias' if d <= 365 else 'Acima de 365 dias'
    def rp_de(n):
        c = {}
        for e in emp_c.get(n, []):
            v = (e.get('RESULTADO_PRIMARIO') or '').strip()
            if v:
                c[v] = c.get(v, 0) + 1
        return max(c, key=c.get) if c else '-'
    COLS_PLAN = ['Código Programa', 'Link Programa', 'Nº Proposta', 'Nº Instrumento', 'Nome Parlamentar', 'Nº Emenda', 'Ano Proposta', 'Link Direto',
                 'Modalidade', 'Nome Proponente', 'CNPJ', 'UF', 'Objeto', 'Nº Processo', 'Situação Instrumento', 'Ação Orçamentária', 'Nome Programa',
                 'Resultado Primário', 'UG', 'Data Assinatura', 'Data Início de Vigência Conv.', 'Data Fim de Vigência Conv.', 'Data Limite Prestação de Contas',
                 'Valor Global', 'Valor de Repasse', 'Valor de Contrapartida', 'Valor Desembolsado Acumulado', 'A Desembolsar', 'Ingresso de Contrapartida',
                 'Rendimento Aplicação', 'Saldo em conta', 'Execução Financeira', 'Último Pagamento', 'Sem Desembolso']
    plan = []
    for r in inst:
        # a planilha Parcerias tem TODOS os instrumentos, em todas as situações (assinados ou não, cancelados, anulados, aguardando assinatura…):
        # alguém pergunta por um número e ele precisa aparecer, com a situação em que está (ex.: 983597, cancelado antes da assinatura)
        ids = [x for x in r['id_programa'].split(' | ') if x]
        emexec = r['situacao'] == 'Em execução'
        d = int(r['dias_sem_desembolso']) if r['dias_sem_desembolso'] else None
        plan.append(dict(zip(COLS_PLAN, [
            r['cod_programa'] or '-',
            ('https://discricionarias.transferegov.sistema.gov.br/voluntarias/ConsultarPrograma/ResultadoDaConsultaDeProgramaDeConvenioDetalhar.do?id=' + ids[0] + '&Usr=guest&Pwd=guest') if ids else '-',
            r['nr_proposta'] or '-', r['nr_instrumento'], r['parlamentar'] or '-', r['nr_emenda'] or '-', r['ano_proposta'] or '-', r['link_proposta'],
            r['modalidade'] or '-', r['proponente'] or '-', r['cnpj_proponente'] or '-', r['uf'] or '-', r['objeto'] or '-', r['nr_processo'] or '-',
            r['situacao'] or r['situacao_proposta'] or '-', r['acao_orcamentaria'] or '-', r['programa'] or '-', rp_de(r['nr_instrumento']), r['ug_emitente'],
            r['data_assinatura'] or '-', r['inicio_vigencia'] or '-', r['fim_vigencia'] or '-', r['limite_prestacao_contas'] or '-',
            r['valor_global'], r['valor_repasse'], r['valor_contrapartida'], r['valor_desembolsado'], r['valor_a_desembolsar'],
            r['ingresso_contrapartida'], r['rendimento_aplicacao'], r['saldo_em_conta'], '',
            ('Sem Desembolso' if emexec and d is None else '-'),
            (faixa(d) if emexec and d is not None else '-')])))
    gravar(saida, 'planilha_parcerias.csv', COLS_PLAN, plan)
    # painel mais leve: o painel não baixa as colunas de link da planilha (42% do tamanho); monta os links por estes ids
    lk = {'prop': {}, 'prog': {}}
    for r in inst:
        if r.get('id_proposta'):
            lk['prop'][r['nr_instrumento']] = r['id_proposta']
        ids = [x for x in (r.get('id_programa') or '').split(' | ') if x]
        if ids and r.get('cod_programa'):
            lk['prog'].setdefault(r['cod_programa'], ids[0])
    with gzip.open(os.path.join(saida, 'parc_links.json.gz'), 'wt', encoding='utf-8', compresslevel=9) as fh:
        json.dump(lk, fh, separators=(',', ':'))
    log(f"gravou parc_links.json.gz · {len(lk['prop'])} instrumentos · {len(lk['prog'])} programas")

    # 7. propostas (todas do escopo, celebradas ou não)
    props = []
    for p in escopo:
        if p not in proposta:
            continue
        reg = info_prop(p)
        n = prop_do_conv.get(p, '')
        c = conv.get(n, {})
        reg.update({'nr_instrumento': n, 'ug_emitente': c.get('UG_EMITENTE', ''), 'situacao_instrumento': c.get('SIT_CONVENIO', ''),
                    'celebrada': 'SIM' if c.get('IND_ASSINADO') == 'SIM' else 'NÃO'})
        props.append(reg)
    props.sort(key=lambda r: (r['ano_proposta'] or '0000', r['nr_proposta']), reverse=True)
    campos_prop = list(props[0].keys()) if props else []
    # o arquivo completo passa de 100 MB (limite do GitHub): um arquivo por ano + "propostas.csv" com os anos recentes
    ano_min = hoje.year - 3
    gravar(saida, 'propostas.csv', campos_prop, [r for r in props if (r['ano_proposta'] or '0') >= str(ano_min)])
    por_ano = {}
    for r in props:
        por_ano.setdefault(r['ano_proposta'] or 'sem_ano', []).append(r)
    os.makedirs(os.path.join(saida, 'propostas_por_ano'), exist_ok=True)
    for ano, lista in sorted(por_ano.items()):
        gravar(saida, os.path.join('propostas_por_ano', f'propostas_{ano}.csv'), campos_prop, lista)
    meta['propostas_por_ano'] = {ano: {'total': len(l), 'celebradas': sum(1 for r in l if r['celebrada'] == 'SIM')} for ano, l in sorted(por_ano.items())}
    meta['propostas_csv_desde'] = ano_min

    # 7b. arquivo no formato da planilha "BASE PROPOSTAS SDR" (colunas A:Y), propostas de 3 anos atrás em diante
    def etapa(r):
        s = (r.get('situacao_proposta') or '').upper()
        if r.get('celebrada') == 'SIM':
            return 'Celebrada'
        if 'REJEIT' in s or 'ELIMINAD' in s:
            return 'Rejeitada'
        if 'CADASTRAD' in s:
            return 'Cadastrada'
        if s.endswith('COMPLEMENTAÇÃO') and 'ENVIAD' not in s and 'ANÁLISE' not in s:
            return 'Em complementação'
        if 'APROVAD' in s and 'ANÁLISE' not in s and 'COMPLEMENTA' not in s:
            return 'Aprovada'
        return 'Enviada / em análise' if s else '(sem situação)'
    AC420 = {'215A', '8593', '214Z', '00PN', '8622', '21B6', '8606'}
    COLS_PROP = ['Nº Proposta', 'Ano', 'Situação no Transferegov', 'Etapa', 'Modalidade', 'Programa', 'Ação orçamentária', 'Parlamentar', 'Nº Emenda',
                 'Tipo de parlamentar', 'Proponente', 'CNPJ', 'Natureza jurídica', 'UF', 'Município', 'Objeto', 'Valor global', 'Repasse proposto',
                 'Contrapartida', 'Início vigência', 'Fim vigência', 'Nº Instrumento', 'UG', 'Situação do instrumento', 'Link da proposta', 'Sugestão acompanhamento']
    plan_p = []
    for r in props:
        if (r['ano_proposta'] or '0') < str(ano_min):
            continue
        acoes = sorted({x.strip()[-4:] for x in (r['acao_orcamentaria'] or '').split('|') if x.strip()})
        plan_p.append(dict(zip(COLS_PROP, [r['nr_proposta'], r['ano_proposta'], r['situacao_proposta'], etapa(r), r['modalidade'], r['programa'],
                                           ' | '.join(acoes), r['parlamentar'], r['nr_emenda'], r['tipo_parlamentar'], r['proponente'], r['cnpj_proponente'],
                                           r['natureza_juridica'], r['uf'], r['municipio'], r['objeto'], r['valor_global_proposta'], r['valor_repasse_proposta'],
                                           r['valor_contrapartida_proposta'], r['inicio_vigencia_proposta'], r['fim_vigencia_proposta'], r['nr_instrumento'],
                                           r['ug_emitente'], r['situacao_instrumento'], r['link_proposta'],
                                           '(atualizar)' if AC420 & set(acoes) else 'Outras UGs'])))
    gravar(saida, 'planilha_propostas.csv', COLS_PROP, plan_p)
    # o Google (gviz) apaga as células do tipo minoritário de cada coluna (ex.: nº de instrumento "7AAHBG" numa coluna de números);
    # o painel lê as abas pelo gviz e completa essas células por este arquivo, pela chave da proposta
    def tipo_cel(v):
        v = str(v or '').strip()
        if not v:
            return None
        if re.fullmatch(r'-?\d+([.,]\d+)?', v):
            return 'n'
        if re.fullmatch(r'\d{2}/\d{2}/\d{4}', v):
            return 'd'
        return 't'
    def minoritarias(linhas, cols, chave):
        out = {}
        for c in cols:
            if c.startswith('Link') or c == chave:
                continue
            cont = {}
            for r in linhas:
                k = tipo_cel(r.get(c))
                if k:
                    cont[k] = cont.get(k, 0) + 1
            if len(cont) < 2:
                continue
            maior = max(cont, key=cont.get)
            for r in linhas:
                k = tipo_cel(r.get(c))
                if k and k != maior and r.get(chave):
                    out.setdefault(r[chave], {})[c] = r[c]
        return out
    fix = {'parc': minoritarias(plan, COLS_PLAN, 'Nº Proposta'), 'prop': minoritarias(plan_p, COLS_PROP, 'Nº Proposta')}
    with gzip.open(os.path.join(saida, 'planilha_celulas.json.gz'), 'wt', encoding='utf-8', compresslevel=9) as fh:
        json.dump(fix, fh, ensure_ascii=False, separators=(',', ':'))
    log(f"gravou planilha_celulas.json.gz · parcerias {len(fix['parc'])} linhas · propostas {len(fix['prop'])} linhas")

    # 8. tabelas de detalhe (colunas originais do Transferegov)
    gravar(saida, 'empenhos.csv', cab_emp or ['NR_CONVENIO'], empenhos)
    # versão leve das notas de empenho para a ficha do painel (nota exata de cada instrumento)
    gravar(saida, 'painel_empenhos.csv', ['nr_instrumento', 'ne', 'ug', 'data', 'tipo', 'situacao', 'valor', 'ptres', 'pi', 'ns_saldo'],
           [{'nr_instrumento': e.get('NR_CONVENIO', ''), 'ne': e.get('NR_EMPENHO', ''), 'ug': e.get('UG_EMITENTE', ''), 'data': e.get('DATA_EMISSAO', ''),
             'tipo': e.get('DESC_TIPO_NOTA', ''), 'situacao': e.get('DESC_SITUACAO_EMPENHO', ''), 'valor': v2(num(e.get('VALOR_EMPENHO'))),
             'ptres': e.get('PTRES', ''), 'pi': e.get('PLANO_INTERNO', ''),
             'ns_saldo': '1' if 'NSSALDO' in (e.get('OBSERVACAO_EMPENHO') or '').upper().replace(' ', '') else ''} for e in empenhos])   # nota gerada pela transferência de saldo entre UGs
    gravar(saida, 'desembolsos.csv', cab_des or ['NR_CONVENIO'], desembolsos)
    # versão leve dos desembolsos para a ficha do painel (ordem bancária de cada desembolso)
    gravar(saida, 'painel_desembolsos.csv', ['nr_instrumento', 'data', 'ob', 'ug', 'obs', 'valor'],
           [{'nr_instrumento': x.get('NR_CONVENIO', ''), 'data': x.get('DATA_DESEMBOLSO', ''), 'ob': x.get('NR_SIAFI', ''), 'ug': x.get('UG_EMITENTE_DH', ''),
             'obs': (x.get('OBSERVACAO_DH') or '')[:300], 'valor': v2(num(x.get('VL_DESEMBOLSADO')))} for x in desembolsos])
    # empenho usado em cada desembolso (siconv_empenho_desembolso: liga ID_DESEMBOLSO a ID_EMPENHO)
    try:
        des_id = {x.get('ID_DESEMBOLSO'): x for x in desembolsos if x.get('ID_DESEMBOLSO')}
        emp_id = {e.get('ID_EMPENHO'): e for e in empenhos if e.get('ID_EMPENHO')}
        cab_ed, it_ed = linhas('siconv_empenho_desembolso')
        ligas = []
        if cab_ed:
            k_des = next((c for c in cab_ed if 'DESEMBOLSO' in c and c.startswith('ID')), 'ID_DESEMBOLSO')
            k_emp = next((c for c in cab_ed if 'EMPENHO' in c and c.startswith('ID')), 'ID_EMPENHO')
            k_val = next((c for c in cab_ed if c.startswith('VALOR') or c.startswith('VL')), None)
            log(f'siconv_empenho_desembolso · colunas: {cab_ed}')
            for r in it_ed:
                d = des_id.get(r.get(k_des))
                if not d:
                    continue
                e = emp_id.get(r.get(k_emp), {})
                ligas.append({'nr_instrumento': d.get('NR_CONVENIO', ''), 'id_desembolso': r.get(k_des), 'ob': d.get('NR_SIAFI', ''),
                              'ne': e.get('NR_EMPENHO', '') or ('id ' + str(r.get(k_emp))), 'valor': v2(num(r.get(k_val))) if k_val else ''})
        gravar(saida, 'empenho_desembolso.csv', ['nr_instrumento', 'id_desembolso', 'ob', 'ne', 'valor'], ligas)
    except Exception as ex:
        log(f'empenho_desembolso não gerado: {ex}')
    gravar(saida, 'aditivos.csv', cab_ta or ['NR_CONVENIO'], aditivos)
    gravar(saida, 'prorrogacoes.csv', cab_pr or ['NR_CONVENIO'], prorrogas)
    gravar(saida, 'historico_situacao.csv', cab_hs or ['NR_CONVENIO'], historico)
    gravar(saida, 'pagamentos.csv', cab_pg or ['NR_CONVENIO'], pagamentos)
    gravar(saida, 'cronograma_desembolso.csv', cab_cr or ['NR_CONVENIO'], cronograma)
    gravar(saida, 'ajustes_pt.csv', cab_aj or ['NR_CONVENIO'], ajustes_pt)
    gravar(saida, 'pad.csv', cab_pad or ['ID_PROPOSTA'], pad)
    gravar(saida, 'licitacoes.csv', cab_lic or ['NR_CONVENIO'], licitacoes)
    gravar(saida, 'contratos_convenente.csv', cab_ctc or ['NR_CONVENIO'], contratos_conv)
    gravar(saida, 'metas.csv', cab_mt or ['ID_META'], metas)
    gravar(saida, 'etapas.csv', cab_et or ['ID_META'], etapas)
    gravar(saida, 'emendas.csv', meta['cabecalhos'].get('emenda') or ['ID_PROPOSTA'], emendas)

    # obras (Obrasgov / acompanhamento de obras): filtra pelo nº do instrumento ou pelo ID da proposta, o que o arquivo tiver
    OBRAS_LINHAS = {}

    def obras_de(nome, saida_nome):
        cab, it = linhas(nome)
        meta['cabecalhos'][nome.replace('siconv_', '')] = cab
        if not cab:
            return 0
        ci = next((c for c in cab if c in ('NR_CONVENIO', 'NR_INSTRUMENTO', 'NUMERO_INSTRUMENTO', 'NR_TRANSFERENCIA')), None) \
            or next((c for c in cab if 'CONVENIO' in c or 'INSTRUMENTO' in c), None)
        cp = 'ID_PROPOSTA' if 'ID_PROPOSTA' in cab else None
        out = [r for r in it if (ci and r.get(ci) in conv) or (cp and r.get(cp) in prop_do_conv)]
        log(f'{nome}: {len(out)} linhas da SDR (chave: {ci or cp})')
        gravar(saida, saida_nome, cab, out)
        OBRAS_LINHAS[saida_nome] = out
        return len(out)
    n_obras = obras_de('siconv_dados_obrasgov_geral', 'obras.csv')
    n_med = obras_de('siconv_acomp_obras_contratos_medicoes_modulo_empresas', 'obras_medicoes.csv')
    n_itm = obras_de('siconv_acomp_obras_valores_itens_medicao_modulo_empresas', 'obras_itens_medicao.csv')
    n_rff = obras_de('siconv_resumo_fisico_financeiro', 'resumo_fisico_financeiro.csv')

    # ---- painel de obras: 1 linha por instrumento com obra, situação calculada e histórico diário do % físico ----
    inst_por_num = {r['nr_instrumento']: r for r in inst}
    conv_da_prop = {p: n for p, n in prop_do_conv.items()}
    ob = {}
    for r in OBRAS_LINHAS.get('obras.csv', []):
        n = str(r.get('NR_INSTRUMENTO', '')).strip()
        if n in conv:
            ob.setdefault(n, {})['link_transparencia'] = r.get('LINK_TRANSPARENCIA', '')
            ob[n]['id_projeto_investimento'] = r.get('ID_PROJETO_INVESTIMENTO', '')
    for r in OBRAS_LINHAS.get('resumo_fisico_financeiro.csv', []):
        n = conv_da_prop.get(r.get('ID_PROPOSTA'))
        if n:
            o = ob.setdefault(n, {})
            o['valor_obra'] = num(r.get('VALOR_TOTAL_RESUMO_FISICO_FINANCEIRO'))
            o['valor_realizado'] = num(r.get('VALOR_REALIZADO_RESUMO_FISICO_FINANCEIRO'))
            o['pct_fisico'] = num(r.get('PERCENTUAL_EXECUCAO_RESUMO_FISICO_FINANCEIRO'))
    for r in OBRAS_LINHAS.get('obras_medicoes.csv', []):
        n = conv_da_prop.get(r.get('ID_PROPOSTA'))
        if not n:
            continue
        o = ob.setdefault(n, {})
        nr = int(num(r.get('NUMERO_MEDICAO_ACOMPANHAMENTO_OBRA')))
        if nr >= o.get('_nr', -1):
            o['_nr'] = nr
            o['nr_medicao'] = str(nr)
            o['situacao_medicao'] = r.get('SITUACAO_MEDICAO_ACOMPANHAMENTO_OBRA', '')
            o['fim_ultima_medicao'] = br(data(r.get('DATA_FIM_MEDICAO_OBJETO_ACOMPANHAMENTO_OBRA')))
            o['dias_sem_medicao'] = r.get('QTD_DIAS_SEM_MEDICAO_ACOMPANHAMENTO_OBRA', '')
            o['inicio_obra'] = br(data(r.get('DATA_INICIO_OBRA_CONTRATO_ACOMPANHAMENTO_OBRA')))
            o['cnpj_empresa'] = r.get('CNPJ_FORNECEDOR_CONTRATO_ACOMPANHAMENTO_OBRA', '')
    # histórico do % físico (guardado de um dia para o outro; arquivo anterior vem pela variável HIST_ANTERIOR)
    hist, hoje_txt = [], hoje.strftime('%Y-%m-%d')
    ant = os.environ.get('HIST_ANTERIOR')
    if ant and os.path.exists(ant):
        with open(ant, encoding='utf-8') as f:
            hist = [r for r in csv.DictReader(f) if r.get('data') != hoje_txt]
    for n, o in ob.items():
        if 'pct_fisico' in o:
            hist.append({'data': hoje_txt, 'nr_instrumento': n, 'pct_fisico': f"{o['pct_fisico']:.2f}", 'valor_realizado': v2(o.get('valor_realizado', 0))})
    limite = (hoje - datetime.timedelta(days=400)).strftime('%Y-%m-%d')
    hist = [r for r in hist if r['data'] >= limite]
    gravar(saida, 'historico_obras.csv', ['data', 'nr_instrumento', 'pct_fisico', 'valor_realizado'], sorted(hist, key=lambda r: (r['nr_instrumento'], r['data'])))
    dias_hist = len(set(r['data'] for r in hist))
    serie = {}
    for r in hist:
        serie.setdefault(r['nr_instrumento'], []).append((r['data'], float(r['pct_fisico'] or 0)))

    def evolucao(n, dias):
        pts = sorted(serie.get(n, []))
        if not pts:
            return None
        alvo = (hoje - datetime.timedelta(days=dias)).strftime('%Y-%m-%d')
        antes = [p for d, p in pts if d <= alvo]
        return None if not antes else pts[-1][1] - antes[-1]

    painel_obras = []
    for n, o in ob.items():
        i = inst_por_num.get(n, {})
        pct = o.get('pct_fisico')
        fim = data(i.get('fim_vigencia'))
        dsm = int(num(o.get('dias_sem_medicao'))) if o.get('dias_sem_medicao') not in (None, '') else None
        e120, e365 = evolucao(n, 120), evolucao(n, 365)
        if pct is not None and pct >= 99.995:
            sit, crit = 'Finalizada', '100% de execução física'
        elif fim and fim < hoje:
            sit, crit = 'Inacabada', 'vigência vencida e obra não concluída (Lei 14.719/2023, art. 2º, II)'
        elif (pct or 0) == 0 and not o.get('nr_medicao'):
            sit, crit = 'Não iniciada', 'sem medição e sem execução física'
        elif (e120 is not None and e120 < 5) or (e365 is not None and e365 < 15):
            sit, crit = 'Paralisada', 'evolução física < 5% em 120 dias ou < 15% em 365 dias (Lei 14.719/2023, art. 2º, I, c)'
        elif e120 is None and dsm is not None and dsm > 120:
            sit, crit = 'Paralisada', f'sem medição há {dsm} dias (critério provisório até completar 120 dias de histórico)'
        else:
            sit, crit = 'Em andamento', ''
        painel_obras.append({
            'nr_instrumento': n, 'situacao_obra': sit, 'criterio': crit,
            'pct_fisico': f"{pct:.2f}" if pct is not None else '', 'valor_obra': v2(o.get('valor_obra', 0)), 'valor_realizado': v2(o.get('valor_realizado', 0)),
            'evolucao_120d': f'{e120:.2f}' if e120 is not None else '', 'evolucao_365d': f'{e365:.2f}' if e365 is not None else '',
            'nr_medicao': o.get('nr_medicao', ''), 'situacao_medicao': o.get('situacao_medicao', ''), 'fim_ultima_medicao': o.get('fim_ultima_medicao', ''),
            'dias_sem_medicao': '' if dsm is None else str(dsm), 'inicio_obra': o.get('inicio_obra', ''), 'cnpj_empresa': o.get('cnpj_empresa', ''),
            'situacao_instrumento': i.get('situacao', ''), 'ug_emitente': i.get('ug_emitente', ''), 'modalidade': i.get('modalidade', ''),
            'fim_vigencia': i.get('fim_vigencia', ''), 'valor_repasse': i.get('valor_repasse', ''), 'valor_desembolsado': i.get('valor_desembolsado', ''),
            'pct_desembolsado': i.get('pct_desembolsado', ''), 'proponente': i.get('proponente', ''), 'uf': i.get('uf', ''), 'municipio': i.get('municipio', ''),
            'cod_ibge': i.get('cod_ibge', ''), 'parlamentar': i.get('parlamentar', ''), 'objeto': (i.get('objeto', '') or '')[:200],
            'id_projeto_investimento': o.get('id_projeto_investimento', ''), 'link_transparencia': o.get('link_transparencia', ''),
        })
    painel_obras.sort(key=lambda r: r['nr_instrumento'], reverse=True)
    gravar(saida, 'painel_obras.csv', list(painel_obras[0].keys()) if painel_obras else ['nr_instrumento'], painel_obras)
    meta['obras_dias_de_historico'] = dias_hist
    meta['obras_por_situacao'] = {k: sum(1 for r in painel_obras if r['situacao_obra'] == k) for k in ('Não iniciada', 'Em andamento', 'Paralisada', 'Inacabada', 'Finalizada')}

    meta['contagens'] = {'obras': n_obras, 'obras_medicoes': n_med, 'obras_itens_medicao': n_itm, 'resumo_fisico_financeiro': n_rff, 'instrumentos': len(inst), 'propostas': len(props), 'empenhos': len(empenhos),
                         'desembolsos': len(desembolsos), 'aditivos': len(aditivos), 'prorrogacoes': len(prorrogas),
                         'emendas': len(emendas), 'programas': len(progs_sdr)}
    meta['log'] = LOG
    with open(os.path.join(saida, 'atualizacao.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    log('fim')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'saida')
