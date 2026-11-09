/**
 * PAINEL DE EXECUÇÃO FINANCEIRA 2027 — base e API (versão de TESTE)
 *
 * Como instalar (uma vez):
 *  1. Crie uma planilha Google nova chamada "BASE EXECUÇÃO 2027".
 *  2. Extensões › Apps Script › apague o conteúdo e cole este arquivo inteiro. Salve.
 *  3. No menu de funções escolha  instalar  e clique em Executar (autorize quando pedir).
 *     Ele cria as abas, cadastra VOCÊ como ADMIN e coloca instrumentos de TESTE.
 *  4. Implantar › Nova implantação › Tipo: App da Web
 *       Executar como: Eu   ·   Quem pode acessar: Qualquer pessoa
 *     Copie o link que termina em /exec e cole no painel na primeira vez que abrir.
 *
 * Perfis (aba USUARIOS, coluna perfil):
 *   ADMIN      → coordenador financeiro e chefe de divisão: vê tudo e distribui
 *   ORCAMENTO  → registra a demanda e confirma o saldo da NE
 *   EXECUTOR   → vê só a própria fila e informa o pagamento
 */

var ANO = 2027;
var ABAS = {
  USUARIOS:     ['email', 'nome', 'perfil', 'ativo'],
  INSTRUMENTOS: ['id', 'tipo', 'ug', 'numero', 'processo_raiz', 'favorecido', 'cnpj', 'objeto', 'vigencia_ini', 'vigencia_fim', 'valor_total', 'media_mensal', 'fiscal', 'origem'],
  NES:          ['instrumento_id', 'ne', 'recurso', 'fonte', 'acao', 'nd', 'saldo'],
  COMPETENCIAS: ['id', 'instrumento_id', 'competencia', 'valor_previsto', 'situacao',
                 'processo_pagamento', 'area_demandante', 'valor', 'ne', 'recurso', 'fonte', 'obs_orcamento', 'orcamento_por', 'orcamento_em',
                 'executor', 'distribuido_por', 'distribuido_em',
                 'obs', 'informado_por', 'informado_em',
                 'tesouro_ob', 'tesouro_valor', 'tesouro_data', 'conferido_em'],
  HISTORICO:    ['quando', 'email', 'acao', 'competencia_id', 'detalhe'],
  TESOURO_OB:   ['ne', 'ob', 'data', 'valor'],
  SESSOES:      ['token', 'email', 'exp']
};
// situações de uma competência
var SIT = { PREVISTO: 'PREVISTO', REFORCO: 'REFORCO', SALDO_OK: 'SALDO_OK', DISTRIBUIDO: 'DISTRIBUIDO', INFORMADO: 'INFORMADO', CONFIRMADO: 'CONFIRMADO', PENDENCIA: 'PENDENCIA' };

/* =========================== INSTALAÇÃO =========================== */

function instalar() {
  var ss = SpreadsheetApp.getActive();
  Object.keys(ABAS).forEach(function (nome) {
    var sh = ss.getSheetByName(nome) || ss.insertSheet(nome);
    var cab = ABAS[nome];
    sh.getRange(1, 1, 1, cab.length).setValues([cab]).setFontWeight('bold').setBackground('#155a30').setFontColor('#ffffff');
    sh.setFrozenRows(1);
  });
  var padrao = ss.getSheetByName('Página1') || ss.getSheetByName('Sheet1');
  if (padrao && ss.getSheets().length > 1) ss.deleteSheet(padrao);

  var eu = Session.getEffectiveUser().getEmail();
  if (!lerTudo('USUARIOS').some(function (u) { return igual(u.email, eu); })) {
    anexar('USUARIOS', { email: eu, nome: 'David (coordenador)', perfil: 'ADMIN', ativo: 'SIM' });
  }
  if (!lerTudo('INSTRUMENTOS').length) carregarTeste();
  SpreadsheetApp.getUi && toast('Instalado. Você foi cadastrado como ADMIN: ' + eu);
}

/** Instrumentos de TESTE (exemplos, não são dados reais). Para limpar: apague as linhas nas abas. */
function carregarTeste() {
  var inst = [
    { id: 'T1', tipo: 'Contrato', ug: '130010', numero: '00/2025', processo_raiz: '21000.000001/2025-00', favorecido: '[TESTE] EMPRESA DE VIGILÂNCIA', cnpj: '00.000.000/0001-00', objeto: 'Vigilância patrimonial', vigencia_ini: '2025-05-14', vigencia_fim: '2027-05-13', valor_total: 2332674, media_mensal: 194389.5, fiscal: '[NOME DO FISCAL]', origem: 'TESTE' },
    { id: 'T2', tipo: 'Contrato', ug: '130010', numero: '00/2017', processo_raiz: '21000.000002/2017-00', favorecido: '[TESTE] DISTRIBUIDORA DE ENERGIA', cnpj: '00.000.000/0002-00', objeto: 'Energia elétrica', vigencia_ini: '2017-01-01', vigencia_fim: '2099-12-31', valor_total: 78000, media_mensal: 6500, fiscal: '[NOME DO FISCAL]', origem: 'TESTE' },
    { id: 'T3', tipo: 'Ata', ug: '130010', numero: 'ATA 02/2025', processo_raiz: '21000.000003/2025-00', favorecido: '[TESTE] FORNECEDOR ATA', cnpj: '00.000.000/0003-00', objeto: 'Água mineral', vigencia_ini: '2025-03-01', vigencia_fim: '2027-03-01', valor_total: 94752, media_mensal: 7896, fiscal: '[NOME DO FISCAL]', origem: 'TESTE' },
    { id: 'T4', tipo: 'Parceria', ug: '420013', numero: 'TF 000000/2026', processo_raiz: '21000.000004/2026-00', favorecido: '[TESTE] ASSOCIAÇÃO', cnpj: '00.000.000/0004-00', objeto: 'Termo de Fomento — apoio à agricultura familiar', vigencia_ini: '2026-06-01', vigencia_fim: '2027-12-31', valor_total: 380000, media_mensal: 0, fiscal: '[GESTOR DA PARCERIA]', origem: 'TESTE' }
  ];
  inst.forEach(function (i) { anexar('INSTRUMENTOS', i); });
  [
    { instrumento_id: 'T1', ne: '2027NE000010', recurso: 'EXE001', fonte: '1000000000', acao: '20ZY · 0003', nd: '33903703', saldo: 1138760.64 },
    { instrumento_id: 'T1', ne: '2026NE000195', recurso: 'RAP001', fonte: '1000000000', acao: '20ZY · 0003', nd: '33903703', saldo: 284690.16 },
    { instrumento_id: 'T2', ne: '2027NE000020', recurso: 'EXE001', fonte: '1000000000', acao: '20ZY · 0003', nd: '33903943', saldo: 52000 },
    { instrumento_id: 'T3', ne: '2025NE000058', recurso: 'RAP001', fonte: '1000000000', acao: '2000 · 000K', nd: '33903007', saldo: 23688 },
    { instrumento_id: 'T4', ne: '2026NE000071', recurso: 'RAP001', fonte: '1000000000', acao: '215A', nd: '33504101', saldo: 190000 }
  ].forEach(function (n) { anexar('NES', n); });
  inst.forEach(function (i) {
    if (i.tipo === 'Parceria') {
      anexar('COMPETENCIAS', novaComp(i.id, ANO + '-03', 190000, '2ª parcela'));
      anexar('COMPETENCIAS', novaComp(i.id, ANO + '-09', 190000, '3ª parcela'));
      return;
    }
    gerarCompetencias(i).forEach(function (c) { anexar('COMPETENCIAS', c); });
  });
}

/** Competências de dez/(ANO-1) a dez/ANO dentro da vigência, com a média mensal. */
function gerarCompetencias(i) {
  var out = [], ini = String(i.vigencia_ini).slice(0, 7), fim = String(i.vigencia_fim).slice(0, 7);
  for (var k = 0; k <= 12; k++) {
    var a = k === 0 ? ANO - 1 : ANO, m = k === 0 ? 12 : k;
    var comp = a + '-' + (m < 10 ? '0' : '') + m;
    if (comp < ini || comp > fim) continue;
    out.push(novaComp(i.id, comp, Number(i.media_mensal) || 0, ''));
  }
  return out;
}
function novaComp(instId, comp, valor, rotulo) {
  return { id: instId + '|' + comp, instrumento_id: instId, competencia: comp, valor_previsto: valor, situacao: SIT.PREVISTO, obs_orcamento: rotulo || '' };
}

/* =========================== API (painel) =========================== */

function doGet() { return json({ ok: true, servico: 'execucao-2027', hora: new Date().toISOString() }); }

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    var p = JSON.parse(e.postData.contents || '{}');
    if (p.acao === 'codigo') return json(pedirCodigo(p));
    if (p.acao === 'entrar') return json(entrar(p));
    var u = usuarioDoToken(p.token);
    if (!u) return json({ ok: false, sessao: false, msg: 'Sessão expirada. Entre de novo.' });
    if (p.acao === 'dados') return json(dados(u));
    lock.waitLock(20000);
    var r;
    if (p.acao === 'demanda') r = registrarDemanda(u, p);
    else if (p.acao === 'distribuir') r = distribuir(u, p);
    else if (p.acao === 'pago') r = informarPago(u, p);
    else if (p.acao === 'desfazer') r = desfazer(u, p);
    else if (p.acao === 'conferir') r = conferirTesouro(u, !!p.simular);
    else r = { ok: false, msg: 'Ação desconhecida.' };
    SpreadsheetApp.flush();
    return json(r);
  } catch (err) {
    return json({ ok: false, msg: 'Erro: ' + err.message });
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}

/* ---- acesso por código no e-mail ---- */
function pedirCodigo(p) {
  var email = String(p.email || '').trim().toLowerCase();
  var u = lerTudo('USUARIOS').filter(function (x) { return igual(x.email, email) && String(x.ativo).toUpperCase() !== 'NÃO'; })[0];
  if (!u) return { ok: false, msg: 'Este e-mail não está cadastrado no painel de execução. Peça ao coordenador.' };
  var cod = String(Math.floor(100000 + Math.random() * 900000));
  CacheService.getScriptCache().put('cod_' + email, cod, 600);
  MailApp.sendEmail({
    to: email,
    subject: 'Código de acesso — Painel de Execução 2027: ' + cod,
    htmlBody: '<p>Seu código para entrar no Painel de Execução Financeira 2027 é:</p><p style="font-size:28px;font-weight:bold;letter-spacing:6px">' + cod + '</p><p>Vale por 10 minutos.</p>'
  });
  return { ok: true };
}
function entrar(p) {
  var email = String(p.email || '').trim().toLowerCase();
  var c = CacheService.getScriptCache(), cod = c.get('cod_' + email);
  if (!cod) return { ok: false, msg: 'Código vencido. Peça um novo.' };
  if (String(p.codigo) !== cod) return { ok: false, msg: 'Código incorreto.' };
  c.remove('cod_' + email);
  var token = Utilities.getUuid(), exp = Date.now() + (p.lembrar ? 30 : 1) * 86400000;
  anexar('SESSOES', { token: token, email: email, exp: exp });
  return { ok: true, token: token, exp: exp };
}
function usuarioDoToken(token) {
  if (!token) return null;
  var s = lerTudo('SESSOES').filter(function (x) { return x.token === token && Number(x.exp) > Date.now(); })[0];
  if (!s) return null;
  var u = lerTudo('USUARIOS').filter(function (x) { return igual(x.email, s.email) && String(x.ativo).toUpperCase() !== 'NÃO'; })[0];
  if (!u) return null;
  return { email: String(u.email).toLowerCase(), nome: u.nome || u.email, perfil: String(u.perfil || 'EXECUTOR').toUpperCase() };
}

/* ---- leitura ---- */
function dados(u) {
  var comps = lerTudo('COMPETENCIAS');
  if (u.perfil === 'EXECUTOR') comps = comps.filter(function (c) { return igual(c.executor, u.email); });
  var ids = {}; comps.forEach(function (c) { ids[c.instrumento_id] = 1; });
  var inst = lerTudo('INSTRUMENTOS'), nes = lerTudo('NES');
  if (u.perfil === 'EXECUTOR') {
    inst = inst.filter(function (i) { return ids[i.id]; });
    nes = nes.filter(function (n) { return ids[n.instrumento_id]; });
  }
  var equipe = lerTudo('USUARIOS').filter(function (x) { return String(x.ativo).toUpperCase() !== 'NÃO' && /EXECUTOR|ADMIN/i.test(x.perfil); })
    .map(function (x) { return { email: String(x.email).toLowerCase(), nome: x.nome || x.email, perfil: String(x.perfil).toUpperCase() }; });
  return { ok: true, eu: u, instrumentos: inst, nes: nes, competencias: comps, equipe: equipe, ano: ANO, atualizado: new Date().toISOString() };
}

/* ---- ações ---- */
function registrarDemanda(u, p) {
  if (!/ADMIN|ORCAMENTO/.test(u.perfil)) return { ok: false, msg: 'Só o Orçamento ou o coordenador registram demanda.' };
  var c = acharComp(p.id); if (!c) return { ok: false, msg: 'Competência não encontrada.' };
  if ([SIT.PREVISTO, SIT.REFORCO, SIT.SALDO_OK].indexOf(c.situacao) < 0) return { ok: false, msg: 'Esta competência já foi distribuída.' };
  if (!p.processo) return { ok: false, msg: 'Informe o processo SEI do pagamento.' };
  var ne = lerTudo('NES').filter(function (n) { return n.instrumento_id === c.instrumento_id && n.ne === p.ne; })[0];
  if (!ne) return { ok: false, msg: 'Escolha a NE.' };
  var ok = !!p.saldoOk;
  atualizarComp(c.id, {
    processo_pagamento: p.processo, area_demandante: p.area || '', valor: Number(p.valor) || c.valor_previsto,
    ne: ne.ne, recurso: ne.recurso, fonte: ne.fonte, obs_orcamento: p.obs || c.obs_orcamento || '',
    orcamento_por: u.email, orcamento_em: agora(), situacao: ok ? SIT.SALDO_OK : SIT.REFORCO
  });
  hist(u, ok ? 'saldo confirmado' : 'reforço solicitado', c.id, p.processo + ' · ' + ne.ne);
  return { ok: true };
}
function distribuir(u, p) {
  if (u.perfil !== 'ADMIN') return { ok: false, msg: 'Só o coordenador e o chefe de divisão distribuem.' };
  var n = 0;
  (p.itens || []).forEach(function (it) {
    var c = acharComp(it.id); if (!c || !it.executor) return;
    if ([SIT.SALDO_OK, SIT.DISTRIBUIDO].indexOf(c.situacao) < 0) return;
    atualizarComp(c.id, { executor: it.executor, distribuido_por: u.email, distribuido_em: agora(), situacao: SIT.DISTRIBUIDO });
    hist(u, 'distribuído', c.id, it.executor); n++;
  });
  return { ok: true, n: n };
}
function informarPago(u, p) {
  var c = acharComp(p.id); if (!c) return { ok: false, msg: 'Competência não encontrada.' };
  if (u.perfil !== 'ADMIN' && !igual(c.executor, u.email)) return { ok: false, msg: 'Este item não está na sua fila.' };
  if ([SIT.DISTRIBUIDO, SIT.PENDENCIA].indexOf(c.situacao) < 0) return { ok: false, msg: 'Este item não está a pagar.' };
  if (!p.processo) return { ok: false, msg: 'Informe o processo SEI do pagamento.' };
  if (!/^(EXE001|RAP001)$/.test(p.recurso || '')) return { ok: false, msg: 'Escolha EXE001 ou RAP001.' };
  atualizarComp(c.id, { processo_pagamento: p.processo, recurso: p.recurso, obs: p.obs || '', informado_por: u.email, informado_em: agora(), situacao: SIT.INFORMADO });
  hist(u, 'informado pago', c.id, p.processo + ' · ' + p.recurso + (p.obs ? ' · ' + p.obs : ''));
  return { ok: true };
}
function desfazer(u, p) {
  var c = acharComp(p.id); if (!c) return { ok: false, msg: 'Competência não encontrada.' };
  if (u.perfil !== 'ADMIN' && !igual(c.informado_por, u.email)) return { ok: false, msg: 'Só quem informou pode desfazer.' };
  if (c.situacao !== SIT.INFORMADO) return { ok: false, msg: 'Só dá para desfazer o que ainda não foi confirmado.' };
  atualizarComp(c.id, { informado_por: '', informado_em: '', situacao: SIT.DISTRIBUIDO });
  hist(u, 'desfeito', c.id, '');
  return { ok: true };
}

/**
 * Conferência com o Tesouro: procura na aba TESOURO_OB (colada do Tesouro Gerencial: NE, OB, data, valor)
 * uma OB da mesma NE com o mesmo valor. Achou → CONFIRMADO. Informado há mais de 3 dias sem OB → PENDENCIA.
 * No teste, "simular" confirma tudo o que estiver INFORMADO com uma OB fictícia.
 * Para rodar todo dia: Acionadores › adicionar › conferirTodoDia › baseado no tempo › diário.
 */
function conferirTesouro(u, simular) {
  if (u && u.perfil !== 'ADMIN') return { ok: false, msg: 'Só o coordenador roda a conferência.' };
  var obs = lerTudo('TESOURO_OB'), usadas = {}, n = 0, pend = 0;
  lerTudo('COMPETENCIAS').forEach(function (c) {
    if (c.situacao !== SIT.INFORMADO && c.situacao !== SIT.PENDENCIA) return;
    var achou = null;
    if (simular) achou = { ob: ANO + 'OB9' + String(Math.floor(Math.random() * 99999)).padStart(5, '0'), data: agora().slice(0, 10), valor: c.valor || c.valor_previsto };
    else obs.some(function (o, k) {
      if (usadas[k] || String(o.ne).trim() !== String(c.ne).trim()) return false;
      if (Math.abs(Number(o.valor) - Number(c.valor || c.valor_previsto)) > 1) return false;
      usadas[k] = 1; achou = o; return true;
    });
    if (achou) {
      atualizarComp(c.id, { tesouro_ob: achou.ob, tesouro_valor: Number(achou.valor), tesouro_data: String(achou.data).slice(0, 10), conferido_em: agora(), situacao: SIT.CONFIRMADO });
      hist(u || { email: 'robô' }, 'confirmado pelo Tesouro', c.id, achou.ob); n++;
    } else if (c.situacao === SIT.INFORMADO && (Date.now() - new Date(c.informado_em).getTime()) > 3 * 86400000) {
      atualizarComp(c.id, { situacao: SIT.PENDENCIA, conferido_em: agora() });
      hist(u || { email: 'robô' }, 'pendência: OB não encontrada', c.id, ''); pend++;
    }
  });
  return { ok: true, confirmados: n, pendencias: pend };
}
function conferirTodoDia() { conferirTesouro(null, false); }

/* =========================== utilitários =========================== */
function sh(n) { return SpreadsheetApp.getActive().getSheetByName(n); }
function lerTudo(n) {
  var s = sh(n); if (!s || s.getLastRow() < 2) return [];
  var v = s.getRange(1, 1, s.getLastRow(), s.getLastColumn()).getValues(), cab = v.shift();
  return v.filter(function (r) { return r.join('') !== ''; }).map(function (r) {
    var o = {}; cab.forEach(function (c, i) { o[c] = r[i] instanceof Date ? Utilities.formatDate(r[i], 'America/Sao_Paulo', "yyyy-MM-dd'T'HH:mm:ss") : r[i]; }); return o;
  });
}
function anexar(n, o) { var cab = ABAS[n]; sh(n).appendRow(cab.map(function (c) { return o[c] === undefined ? '' : o[c]; })); }
function acharComp(id) { return lerTudo('COMPETENCIAS').filter(function (c) { return c.id === id; })[0]; }
function atualizarComp(id, campos) {
  var s = sh('COMPETENCIAS'), v = s.getDataRange().getValues(), cab = v[0];
  for (var r = 1; r < v.length; r++) {
    if (v[r][0] !== id) continue;
    Object.keys(campos).forEach(function (k) { var c = cab.indexOf(k); if (c >= 0) s.getRange(r + 1, c + 1).setValue(campos[k]); });
    return;
  }
}
function hist(u, acao, id, det) { anexar('HISTORICO', { quando: agora(), email: u.email, acao: acao, competencia_id: id, detalhe: det }); }
function agora() { return Utilities.formatDate(new Date(), 'America/Sao_Paulo', "yyyy-MM-dd'T'HH:mm:ss"); }
function igual(a, b) { return String(a || '').trim().toLowerCase() === String(b || '').trim().toLowerCase(); }
function json(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
function toast(t) { try { SpreadsheetApp.getActive().toast(t, 'Execução 2027', 8); } catch (e) {} }
