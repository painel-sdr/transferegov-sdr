
// ===================== cartões clicáveis: clicar num cartão mostra a lista do que ele soma =====================
// a página preenche KPI_DEF[chave] = {tit, lista, cols} a cada render e marca o cartão com data-kpi="chave"
var KPI_DEF = window.KPI_DEF || {}; window.KPI_DEF = KPI_DEF;
function kpiDepois(){
  document.querySelectorAll('[data-kpi]').forEach(c => { c.classList.add('kpi-cl'); c.classList.toggle('kpi-on', c.dataset.kpi === window.__kpi); });
  let box = document.getElementById('kpLista');
  if(!box){ const ref = document.querySelector('[data-kpi]'); if(!ref) return; const grade = ref.closest('.kp') || ref.parentElement;
    box = document.createElement('div'); box.id = 'kpLista'; grade.parentNode.insertBefore(box, grade.nextSibling); }
  // a caixa fica logo abaixo da fileira do cartão clicado
  const on = window.__kpi && document.querySelector(`[data-kpi="${window.__kpi}"]`);
  if(on){ const grade = on.closest('.kp') || on.parentElement; if(grade.nextSibling !== box) grade.parentNode.insertBefore(box, grade.nextSibling); }
  const d = window.__kpi && (window.KPI_DEF||{})[window.__kpi];
  if(!d){ box.innerHTML = ''; return; }
  if(KF.__on !== window.__kpi) KF = {__on: window.__kpi};
  const foco = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.kf : null;
  const LF = kpiFiltrar(d.lista), cols = kpiCols(d), fil = LF.length !== d.lista.length;
  const uniq = a => [...new Set(a)].filter(x => x && x !== '—');
  const mods = uniq(d.lista.map(o => kTipo(o)[0])).sort(), anos = uniq(d.lista.map(o => String(o.ano||''))).sort().reverse();
  const ufs = uniq(d.lista.map(o => String(o.uf||''))).sort(), sits = uniq(d.lista.map(o => String(o.sit||o.fase||''))).sort(), fins = uniq(d.lista.map(kFin)), anosE = uniq(d.lista.flatMap(kAnos).map(String)).sort().reverse();
  const sel = (k, vals, rot) => `<label>${rot}<select data-kf="${k}"><option value="">Todos</option>${vals.map(v => `<option${KF[k]===v?' selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
  const finOps = fins.length ? ['EXE','RAP','EXE e RAP'].concat(fins.filter(v => !/EXE|RAP/.test(v))) : [];
  const met = kpiMetrica(d, cols);
  const nI = x => x.toLocaleString('pt-BR');
  const mc = (rot, cor, v, sub, cls) => `<div class="${cls||''}" style="--c:${cor}"${met ? ` title="${esc(rot)}: ${esc(kBRL(v))}"` : ''}><small>${rot}</small><b>${met ? (Math.abs(v) < 0.005 ? 'R$ 0,00' : 'R$ '+fm(v)) : nI(v)}</b><span>${sub}</span></div>`;
  const vL = l => met ? l.reduce((a,o) => a + met(o), 0) : l.length;
  let mini = mc(fil ? 'Filtrado' : 'Total', fil ? '#e67e22' : '#1f4e79', vL(LF), (fil ? 'de '+(met ? fm(vL(d.lista)) : nI(d.lista.length))+' · ' : '')+(met ? nI(LF.length) : ''), fil ? 'fil' : 'tot');
  if(fins.length) [['EXE','#1f4e79'],['RAP','#8e44ad'],['EXE e RAP','#16756b']].forEach(([k,c]) => { const l = LF.filter(o => kFin(o) === k); mini += mc(k, c, vL(l), met ? nI(l.length) : ''); });
  mini = `<div class="kpi-mc">${mini}</div>`;
  const limpa = Object.keys(KF).some(k => k !== '__on' && KF[k]) ? '<button type="button" class="kpi-bt" data-kflimpa="1">Limpar</button>' : '';
  box.innerHTML = `<section class="card kpi-box"><div class="kpi-cab"><div><h3>📋 ${esc(d.tit)}</h3><p class="d">${fil ? LF.length.toLocaleString('pt-BR')+' de ' : ''}${d.lista.length.toLocaleString('pt-BR')} registro(s) · clique na linha para abrir a ficha</p></div>
    <div><button type="button" class="kpi-bt" data-kpicsv="1">⬇ Extração em Excel</button><button type="button" class="kpi-bt" data-kpifecha="1">✕ Fechar</button></div></div>
    <div class="kpi-fil"><label>Instrumento<input type="search" data-kf="q" data-bm-in="kpi" value="${esc(KF.q||'')}" placeholder="nº, proponente… (vários: ;)" title="Vários termos: separe por ; ou , ou cole uma coluna do Excel · use + para exigir os dois"></label>
    ${sits.length > 1 ? sel('sit', sits, 'Situação') : ''}${mods.length ? sel('mod', mods, 'Modalidade') : ''}${ufs.length > 1 ? sel('uf', ufs, 'UF') : ''}${finOps.length ? sel('fin', finOps, 'Financeiro') : ''}${anos.length ? sel('ano', anos, mods.length ? 'Ano da proposta' : 'Ano') : ''}${anosE.length ? sel('anoNE', anosE, 'Ano do empenho') : ''}${limpa}</div>${mini}
    <div data-bm="kpi"></div>${tabela('k', LF, cols, 10)}</section>`;
  BM.pintar('kpi'); BM.realcar(box.querySelector('table'), 'kpi');
  if(foco){ const x = box.querySelector(`[data-kf="${foco}"]`); if(x){ x.focus(); if(x.type === 'search'){ const n = x.value.length; try{ x.setSelectionRange(n, n); }catch(e){} } } }
}
// ---- filtros, modalidade, financeiro (EXE/RAP) e resumo em valor: mesmo padrão do painel de Parcerias
var KF = {};
const kBRL = v => 'R$ '+Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
function kTipo(o){ const m = String(o && o.mod || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
  return /FOMENTO/.test(m) ? ['Termo de Fomento','#2e7d32'] : /REPASSE/.test(m) ? ['Contrato de Repasse','#b8650a'] : /COLABORA/.test(m) ? ['Termo de Colaboração','#6a3d9a'] : /CONVENIO/.test(m) ? ['Convênio','#1f4e79'] : m ? [o.mod,'#666'] : ['—','']; }
function kAnos(o){ return [...new Set((o && o.nes || []).map(x => { const t = Array.isArray(x) ? x.find(v => /^\d{4}NE/.test(String(v))) : x; return +((String(t||'').match(/^(\d{4})NE/)||[])[1]||0); }).filter(Boolean))].sort(); }
function kFin(o){
  const anos = kAnos(o);
  if(!anos.length) return '—';
  const a = new Date().getFullYear(), e = anos.includes(a), r = anos.some(x => x < a);
  return e && r ? 'EXE e RAP' : e ? 'EXE' : 'RAP';
}
function kpiFiltrar(L){
  return BM.filtrar('kpi', KF.q, L.filter(o => true
    && (!KF.mod || kTipo(o)[0] === KF.mod)
    && (!KF.fin || (KF.fin === 'EXE' ? /EXE/.test(kFin(o)) : KF.fin === 'RAP' ? /RAP/.test(kFin(o)) : kFin(o) === KF.fin))
    && (!KF.ano || String(o.ano||'') === KF.ano)
    && (!KF.anoNE || kAnos(o).includes(+KF.anoNE))
    && (!KF.sit || String(o.sit||o.fase||'') === KF.sit)
    && (!KF.uf || String(o.uf||'') === KF.uf)), o => [o.n, o.num, o.prop, o.parl, o.munN, o.objr, o.obj, o.ent, o.uf, o.ug].join(' '));
}
const kTag = (t, c) => `<span style="display:inline-block;background:${c};color:#fff;font-size:10.5px;font-weight:700;padding:1px 8px;border-radius:10px;white-space:nowrap">${esc(t)}</span>`;
function kpiCols(d){
  let c = d.cols.slice();
  if(d.lista.some(o => o.mod) && !c.some(x => /modalidade/i.test(x[0]))) c.splice(1, 0, ['Modalidade', o => { const t = kTipo(o); return t[1] ? kTag(t[0], t[1]) : '—'; }]);
  if(d.lista.some(o => kFin(o) !== '—') && !c.some(x => /^financeiro$/i.test(x[0]))) c.splice(c.findIndex(x => /modalidade/i.test(x[0])) + 1 || 1, 0, ['Financeiro', o => { const an = kAnos(o), a = new Date().getFullYear(); if(!an.length) return '<small>—</small>';
    const rap = an.filter(x => x < a); return (rap.length ? kTag('RAP '+rap.join(' · '), '#8e44ad')+' ' : '') + (an.includes(a) ? kTag('EXE '+a, '#1f4e79') : ''); }]);
  if(d.lista.some(o => o.ug) && !c.some(x => /^ug\b/i.test(x[0]))){ const i = c.findIndex(x => /^financeiro$/i.test(x[0])); c.splice(i >= 0 ? i+1 : (c.findIndex(x => /modalidade/i.test(x[0])) + 1 || 1), 0, ['UG', o => o.ug ? `<b>${esc(o.ug)}</b>` : '—']); }
  if(d.lista.some(o => o.uf) && !c.some(x => /^uf$/i.test(x[0]))){ const i = c.findIndex(x => /^(ug|financeiro)$/i.test(x[0])); c.splice(i >= 0 ? i+1 : 1, 0, ['UF', o => o.uf ? `<b>${esc(o.uf)}</b>` : '—']); }
  return c;
}
// valor do resumo: coluna de valor com o mesmo nome do cartão (senão a última coluna de valor); lê o número já formatado (Bi/Mi/Mil)
function kpiNum(t){ t = String(t||'').replace(/<small[\s\S]*$/i, '').replace(/<[^>]+>/g, ' ').trim(); const m = t.match(/^([−-])?\s*(?:R\$\s*)?([\d.]+(?:,\d+)?)\s*(Bi|Mi|Mil)?\b/); if(!m) return null;
  let v = parseFloat(m[2].replace(/\./g, '').replace(',', '.')); v *= m[3]==='Bi' ? 1e9 : m[3]==='Mi' ? 1e6 : m[3]==='Mil' ? 1e3 : 1; return m[1] ? -v : v; }
function kpiMetrica(d, cols){
  const ehValor = c => c[2] === 'n' && d.lista.slice(0, 20).some(o => /\b(Bi|Mi|Mil)\b|R\$/.test(String(c[1](o))));
  const norm = s => String(s||'').replace(/<[^>]+>/g, '').trim().toLowerCase();
  const vs = cols.filter(ehValor); if(!vs.length) return null;
  const c = vs.find(x => norm(x[0]) === norm(d.tit)) || vs.find(x => norm(d.tit).includes(norm(x[0]))) || vs[vs.length - 1];
  return o => kpiNum(c[1](o)) || 0;
}
(function(){
  const css = document.createElement('style');
  css.textContent = `.kpi-cl{cursor:pointer;transition:transform .12s, box-shadow .12s}.kpi-cl:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(20,40,60,.16)}
  .kpi-on{outline:3px solid #2fae5c;outline-offset:-3px}.kpi-box{border:2px solid #2fae5c}.kpi-cab{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap}
  .kpi-bt{border:1px solid #b9c7d3;background:#fff;color:#1f4e79;font:600 12.5px inherit;font-family:inherit;padding:6px 12px;border-radius:8px;cursor:pointer;margin-left:6px}
  .kpi-fil{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:flex-end;margin:6px 0 10px}.kpi-fil label{display:flex;flex-direction:column;font-size:11px;font-weight:600;color:#33475b;gap:3px}
  .kpi-fil input,.kpi-fil select{font:inherit;font-size:12px;font-weight:400;padding:5px 8px;border:1px solid #cfd8e3;border-radius:6px;background:#f7f9fb;width:150px;min-width:0;max-width:150px;box-sizing:border-box;text-overflow:ellipsis}
  .kpi-mc{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px}.kpi-mc>div{flex:1;min-width:150px;border:1px solid #dfe6ee;border-left:4px solid var(--c);background:#fafcfd;padding:5px 10px}.kpi-mc>div.fil{background:#fff8ec}.kpi-mc>div.tot{background:#eef3f8}.kpi-mc small{display:block;font-size:10px;font-weight:700;color:#5b6b7b;text-transform:uppercase}.kpi-mc b{font-size:15px;color:#14324f}.kpi-mc span{font-size:10px;color:#7a8794;margin-left:4px}`;
  document.head.appendChild(css);
  const _render = render;
  render = function(){ _render.apply(this, arguments); try{ kpiDepois(); }catch(e){ console.error(e); } };
  document.addEventListener('click', e => {
    const k = e.target.closest('[data-kpi]');
    if(k){ e.stopImmediatePropagation(); window.__kpi = window.__kpi === k.dataset.kpi ? null : k.dataset.kpi; if(typeof PAG === 'object') PAG.k = 0; kpiDepois();
      const b = document.getElementById('kpLista'); if(b && window.__kpi) b.scrollIntoView({block:'nearest', behavior:'smooth'}); return; }
    if(e.target.closest('[data-kpifecha]')){ e.stopImmediatePropagation(); window.__kpi = null; kpiDepois(); return; }
    if(e.target.closest('[data-kflimpa]')){ e.stopImmediatePropagation(); KF = {__on: window.__kpi}; if(typeof PAG === 'object') PAG.k = 0; kpiDepois(); return; }
    if(e.target.closest('[data-kpicsv]')){ e.stopImmediatePropagation(); const d = (window.KPI_DEF||{})[window.__kpi]; if(!d) return;
      const txt = s => String(s ?? '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
      const cs = kpiCols(d), lista = kpiFiltrar(d.lista);
      // Excel no modelo padrão do painel (mesmo das outras telas): valores em número exato, não "50,00 Mi"
      const P = (() => { try{ return window.parent && window.parent !== window && window.parent.baixarXlsx ? window.parent : null; }catch(e){ return null; } })();
      if(P){
        window.__FM_EXATO = true; let L2;
        try{ L2 = lista.map(o => cs.map(c => { const t = txt(c[1](o)), m = t.match(/^§(-?[\d.e+-]+)/); return m ? +m[1] : t.replace(/§(-?[\d.e+-]+)/g, (_, x) => Number(x).toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2})); })); }
        finally{ window.__FM_EXATO = false; }
        const num = cs.map((c, i) => L2.length && L2.every(l => typeof l[i] === 'number' || l[i] === ''));
        P.baixarXlsx({titulo:(document.title || 'Painel SDR') + ' · ' + txt(d.tit || 'lista'), sub:document.title || '', arquivo:(d.tit || 'lista').replace(/[^\wÀ-ú ]+/g, '').trim().replace(/\s+/g, '_'),
          cab:cs.map((c, i) => num[i] ? {t:txt(c[0]), n:1} : {t:txt(c[0])}), linhas:L2});
        return;
      }
      const linhas = [cs.map(c => txt(c[0]))].concat(lista.map(o => cs.map(c => txt(c[1](o)))));
      const csv = '﻿' + linhas.map(l => l.map(v => '"' + v.replace(/"/g, '""') + '"').join(';')).join('\r\n');
      const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); a.download = (d.tit || 'lista').replace(/[^\wÀ-ú ]+/g, '').trim().replace(/\s+/g, '_') + '.csv';
      document.body.appendChild(a); a.click(); a.remove(); return; }
  }, true);
  let tmK; const mudaK = e => { const x = e.target.closest && e.target.closest('[data-kf]'); if(!x) return; e.stopImmediatePropagation();
    KF[x.dataset.kf] = x.value; if(typeof PAG === 'object') PAG.k = 0; clearTimeout(tmK); tmK = setTimeout(kpiDepois, x.type === 'search' ? 250 : 0); };
  document.addEventListener('input', mudaK, true); document.addEventListener('change', mudaK, true);
})();

// ===================== listas: Extração em Excel e PDF + filtros da lista (25/11/2026 · por enquanto só no painel de teste) =====================
// cada tabela(id, L, cols) registra a lista inteira (não só a página visível); os botões exportam o que está filtrado
function tbxTeste(){ try{ return /\/teste\//.test(top.location.pathname); }catch(e){ return false; } }
function tbxReg(id, L, cols){ (window.TBX || (window.TBX = {}))[id] = {L: L, cols: cols}; }
function tbxBar(id, L){
  if(!tbxTeste()) return '';
  return '<div class="tbx-bar"><span>' + Number(L.length).toLocaleString('pt-BR') + ' registro(s)</span><button type="button" class="tbx-xl" data-tbxl="' + id + '">Extração em Excel</button><button type="button" class="tbx-pdf" data-tbxp="' + id + '">Extração em PDF</button></div>';
}
function tbxDados(id){
  var T = (window.TBX || {})[id]; if(!T) return null;
  var txt = function(s){ return String(s == null ? '' : s).replace(/<small[^>]*>/g, ' · ').replace(/<br\s*\/?>/g, ' · ').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/\s+/g, ' ').replace(/^ · | · $/g, '').trim(); };
  var L2; window.__FM_EXATO = true;
  try{ L2 = T.L.map(function(o){ return T.cols.map(function(c){ var t = txt(c[1](o)), m = t.match(/^§(-?[\d.e+-]+)/); if(m) return +m[1];
    return t.replace(/§(-?[\d.e+-]+)/g, function(_, x){ return Number(x).toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2}); }); }); }); }
  finally{ window.__FM_EXATO = false; }
  var num = T.cols.map(function(c, i){ return L2.length > 0 && L2.every(function(l){ return typeof l[i] === 'number' || l[i] === ''; }); });
  var sec = document.querySelector('[data-tbxl="' + id + '"]'); sec = sec && sec.closest('section');
  var tit = (sec && sec.querySelector('h3') ? txt(sec.querySelector('h3').innerHTML) : 'Lista');
  var filtros = [];
  try{ (typeof FIL === 'object' ? FIL : []).forEach(function(f){ var s = typeof _selArr === 'function' ? _selArr(f[0]) : null; if(s) filtros.push(f[1] + ': ' + s.map(function(v){ return typeof _rotF === 'function' ? _rotF(f[0], v) : v; }).join(', ')); }); }catch(e){}
  Object.keys((window.LFS || {})[id] || {}).forEach(function(k){ var s = LFS[id][k]; if(s && s.length){ var d = ((window.LFD || {})[id] || []).find(function(x){ return x[0] === k; }); filtros.push((d ? d[1] : k) + ': ' + s.join(', ')); } });
  var b = sec && sec.querySelector('input.busca'); if(b && b.value.trim()) filtros.push('Busca: "' + b.value.trim() + '"');
  var nome = tit.replace(/[^\wÀ-ú ]+/g, '').trim().replace(/\s+/g, '_');
  return {titulo: (document.title || 'Painel SDR') + ' · ' + tit, sub: document.title || '', arquivo: nome, filtros: filtros,
    cab: T.cols.map(function(c, i){ return num[i] ? {t: txt(c[0]), n: 1} : {t: txt(c[0])}; }), linhas: L2,
    tot: num.some(Boolean) ? T.cols.map(function(c, i){ return i === 0 ? 'Total' : num[i] ? L2.reduce(function(a, l){ return a + (+l[i] || 0); }, 0).toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2}) : ''; }) : null, total: L2.length};
}
// filtros da própria lista (escolha múltipla com busca e contagem): defs = [[campo, rótulo, fn(o) opcional]]
function lfFiltrar(id, defs, L){
  (window.LFD || (window.LFD = {}))[id] = defs; var S = ((window.LFS || (window.LFS = {}))[id] || (LFS[id] = {}));
  var v = function(o, d){ return String((d[2] ? d[2](o) : o[d[0]]) || '—'); };
  return L.filter(function(o){ return defs.every(function(d){ var s = S[d[0]]; return !s || !s.length || s.indexOf(v(o, d)) >= 0; }); });
}
function lfHTML(id, L){
  if(!tbxTeste()) return '';
  var defs = (window.LFD || {})[id] || [], S = (window.LFS || {})[id] || {}, ab = window.__lfab;
  var v = function(o, d){ return String((d[2] ? d[2](o) : o[d[0]]) || '—'); };
  return '<div class="lf">' + defs.map(function(d){
    var s = S[d[0]] || [], rot = !s.length ? 'Todos' : s.length === 1 ? s[0] : s.length + ' selecionados';
    var pop = '';
    if(ab === id + '|' + d[0]){
      var base = L.filter(function(o){ return defs.every(function(e){ var ss = S[e[0]]; return e[0] === d[0] || !ss || !ss.length || ss.indexOf(v(o, e)) >= 0; }); });
      var c = {}; base.forEach(function(o){ var k = v(o, d); c[k] = (c[k] || 0) + 1; }); s.forEach(function(k){ if(!(k in c)) c[k] = 0; });
      var q = String((window.__lfq || '')).normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
      var ops = Object.keys(c).filter(function(k){ return !q || k.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().indexOf(q) >= 0; })
        .sort(function(a, b){ return (s.indexOf(b) >= 0) - (s.indexOf(a) >= 0) || c[b] - c[a] || a.localeCompare(b, 'pt'); }).slice(0, 300);
      pop = '<div class="lf-pop"><input class="lf-q" data-lfq="' + id + '|' + d[0] + '" placeholder="Buscar…" value="' + esc(window.__lfq || '') + '"><div class="lf-l">' + ops.map(function(k){
        return '<label><input type="checkbox" data-lfop="' + id + '|' + d[0] + '" value="' + esc(k) + '"' + (s.indexOf(k) >= 0 ? ' checked' : '') + '><span>' + esc(k) + '</span><em>' + c[k] + '</em></label>'; }).join('') +
        '</div><div class="lf-a"><a data-lflimpa="' + id + '|' + d[0] + '">limpar</a><a data-lffecha="1">fechar ✕</a></div></div>';
    }
    return '<div class="lf-f"><span>' + d[1] + '</span><button type="button" class="' + (s.length ? 'on' : '') + '" data-lfab="' + id + '|' + d[0] + '"><b>' + esc(rot) + '</b><i>▾</i></button>' + pop + '</div>'; }).join('') +
    (Object.keys(S).some(function(k){ return S[k] && S[k].length; }) ? '<button type="button" class="lf-limpa" data-lflimpatudo="' + id + '">Limpar</button>' : '') + '</div>';
}
(function(){
  var st = document.createElement('style');
  st.textContent = '.tbx-bar{display:flex;justify-content:flex-end;align-items:center;gap:8px;margin:0 0 8px;font-size:12px;color:#66727c}.tbx-bar span{margin-right:auto}' +
    '.tbx-bar button{border:0;border-radius:8px;padding:7px 12px;font:inherit;font-size:12.5px;font-weight:700;color:#fff;cursor:pointer}.tbx-xl{background:#1e7a43}.tbx-pdf{background:#a32d2d}' +
    '.lf{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin:0 0 10px}.lf-f{position:relative;display:flex;flex-direction:column;gap:3px;font-size:12px;font-weight:600;color:#3a4a55;min-width:150px}' +
    '.lf-f>button{display:flex;justify-content:space-between;gap:6px;font:inherit;font-weight:500;font-size:13px;padding:6px 9px;border:1px solid #c9d3db;border-radius:8px;background:#f6f8fa;cursor:pointer;text-align:left}.lf-f>button b{font-weight:inherit;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:190px}.lf-f>button.on{border-color:#1f4e79;background:#e3edf7;font-weight:700}.lf-f>button i{font-style:normal;color:#7b8790}' +
    '.lf-pop{position:absolute;top:100%;left:0;z-index:50;width:300px;background:#fff;border:1px solid #c9d6e2;border-radius:10px;box-shadow:0 12px 30px rgba(0,0,0,.2);padding:8px;margin-top:4px;font-weight:400}' +
    '.lf-q{width:100%;box-sizing:border-box;border:1px solid #cfd8e3;border-radius:7px;padding:6px 8px;font:inherit;margin-bottom:6px}.lf-l{max-height:260px;overflow:auto}.lf-l label{display:flex;gap:7px;align-items:center;padding:4px;border-radius:5px;cursor:pointer}.lf-l label:hover{background:#eef5ff}.lf-l span{flex:1}.lf-l em{font-style:normal;font-size:11px;color:#5a6672;background:#eef2f6;border-radius:8px;padding:0 6px}' +
    '.lf-a{display:flex;justify-content:flex-end;gap:12px;border-top:1px solid #eef1f3;margin-top:6px;padding-top:6px}.lf-a a{cursor:pointer;color:#1f4e79;font-weight:600}.lf-limpa{border:1px solid #c9d3db;background:#fff;border-radius:8px;padding:6px 12px;font:inherit;font-size:12.5px;cursor:pointer}' +
    '.lf-res{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:0 0 10px}.lf-res div{background:#f4f7fa;border-left:4px solid var(--c);border-radius:8px;padding:8px 12px}.lf-res small{display:block;font-size:11px;font-weight:700;color:#5a6672;text-transform:uppercase;letter-spacing:.04em}.lf-res b{font-size:17px;color:#14231b}.lf-res span{display:block;font-size:11px;color:#7b8790}';
  document.head.appendChild(st);
  var redesenhar = function(){ if(typeof render === 'function') render(); };
  document.addEventListener('click', function(e){
    var x = e.target.closest && e.target.closest('[data-tbxl],[data-tbxp]');
    if(x){ e.stopImmediatePropagation(); var id = x.dataset.tbxl || x.dataset.tbxp, o = tbxDados(id); if(!o) return;
      var P = null; try{ P = window.parent !== window ? window.parent : null; }catch(er){}
      if(x.dataset.tbxl){ if(P && P.baixarXlsx) return P.baixarXlsx(o);
        var csv = '﻿' + [o.cab.map(function(c){ return c.t; })].concat(o.linhas).map(function(l){ return l.map(function(v){ return '"' + String(v).replace(/"/g, '""') + '"'; }).join(';'); }).join('\r\n');
        var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); a.download = o.arquivo + '.csv'; document.body.appendChild(a); a.click(); a.remove(); return; }
      if(P && P.__listaPDF) return P.__listaPDF(Object.assign({}, o, {linhas: o.linhas.map(function(l){ return l.map(function(v){ return typeof v === 'number' ? v.toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2}) : v; }); })}));
      window.print(); return; }
    var ab = e.target.closest && e.target.closest('[data-lfab]');
    if(ab){ e.stopImmediatePropagation(); window.__lfab = window.__lfab === ab.dataset.lfab ? null : ab.dataset.lfab; window.__lfq = ''; redesenhar(); var q = document.querySelector('.lf-q'); if(q) q.focus(); return; }
    var li = e.target.closest && e.target.closest('[data-lflimpa]');
    if(li){ e.stopImmediatePropagation(); var p = li.dataset.lflimpa.split('|'); delete LFS[p[0]][p[1]]; if(typeof PAG === 'object') PAG[p[0]] = 0; redesenhar(); return; }
    var lt = e.target.closest && e.target.closest('[data-lflimpatudo]');
    if(lt){ e.stopImmediatePropagation(); LFS[lt.dataset.lflimpatudo] = {}; window.__lfab = null; if(typeof PAG === 'object') PAG[lt.dataset.lflimpatudo] = 0; redesenhar(); return; }
    if(e.target.closest && e.target.closest('[data-lffecha]')){ e.stopImmediatePropagation(); window.__lfab = null; redesenhar(); return; }
    if(window.__lfab && !(e.target.closest && e.target.closest('.lf-pop'))){ window.__lfab = null; redesenhar(); }
  }, true);
  document.addEventListener('change', function(e){ var c = e.target.closest && e.target.closest('[data-lfop]'); if(!c) return; e.stopImmediatePropagation();
    var p = c.dataset.lfop.split('|'), S = LFS[p[0]], s = S[p[1]] || (S[p[1]] = []), i = s.indexOf(c.value); if(c.checked && i < 0) s.push(c.value); if(!c.checked && i >= 0) s.splice(i, 1);
    if(typeof PAG === 'object') PAG[p[0]] = 0; redesenhar(); }, true);
  var tq; document.addEventListener('input', function(e){ var q = e.target.closest && e.target.closest('[data-lfq]'); if(!q) return; e.stopImmediatePropagation(); window.__lfq = q.value;
    clearTimeout(tq); tq = setTimeout(function(){ redesenhar(); var n = document.querySelector('.lf-q'); if(n){ n.focus(); var k = n.value.length; try{ n.setSelectionRange(k, k); }catch(er){} } }, 200); }, true);
})();
