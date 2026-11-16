
// ===================== filtro inteligente: busca dentro do filtro, várias escolhas, contagem de cada opção =====================
// (funções declaradas: valem para a página inteira; substituem filtrar/desenharFiltros da página)
function _selArr(k){ const s = SEL[k]; if(s === undefined || s === null || s === '') return null; if(!Array.isArray(s)) SEL[k] = [String(s)]; return SEL[k].length ? SEL[k] : null; }
function ehSel(k, v){ const s = _selArr(k); return !!(s && s.includes(String(v))); }
function alternar(k, v){ v = String(v); const s = _selArr(k) || (SEL[k] = []); const i = s.indexOf(v); if(i >= 0) s.splice(i, 1); else s.push(v); if(!SEL[k].length) delete SEL[k]; }
function _baseF(){ return typeof base === 'function' ? base() : D; }
function filtrar(exceto){
  const at = FIL.filter(([k]) => k !== exceto && _selArr(k)).map(([k]) => [k, new Set(SEL[k])]);
  return _baseF().filter(o => at.every(([k, s]) => Array.isArray(o[k]) ? o[k].some(x => s.has(String(x))) : s.has(String(o[k]))));
}
function _rotF(k, v){ return (typeof ROTULO_F === 'object' && ROTULO_F[k]) ? ROTULO_F[k](v) : v; }
const _semAc = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
function _opcoesF(k){
  const c = new Map(); filtrar(k).forEach(o => (Array.isArray(o[k]) ? o[k] : [o[k]]).forEach(x => { const v = String(x); c.set(v, (c.get(v) || 0) + 1); }));
  (_selArr(k) || []).forEach(v => { if(!c.has(v)) c.set(v, 0); });
  return [...c.entries()].sort((a, b) => /^ano/i.test(k) ? b[0].localeCompare(a[0]) : (b[1] - a[1]) || a[0].localeCompare(b[0], 'pt'));
}
function _listaF(k){
  const q = _semAc((window.__fbus || {})[k] || ''), sel = new Set(_selArr(k) || []);
  let ops = _opcoesF(k); if(q) ops = ops.filter(([v]) => _semAc(_rotF(k, v)).includes(q));
  ops.sort((a, b) => (sel.has(b[0]) - sel.has(a[0])));
  const mostrar = ops.slice(0, 300);
  return mostrar.map(([v, n]) => `<label class="fop ${sel.has(v) ? 'on' : ''}"><input type="checkbox" data-fop="${k}" value="${esc(v)}" ${sel.has(v) ? 'checked' : ''}><span>${esc(_rotF(k, v)) || '(vazio)'}</span><em>${n.toLocaleString('pt-BR')}</em></label>`).join('')
    + (ops.length > 300 ? `<p class="fmais">mostrando 300 de ${ops.length.toLocaleString('pt-BR')} · digite para achar</p>` : '') + (!ops.length ? '<p class="fmais">nada encontrado</p>' : '');
}
function desenharFiltros(){
  const ab = window.__fab;
  document.getElementById('filtros').innerHTML = FIL.map(([k, n, novo]) => {
    const s = _selArr(k), rot = !s ? 'Todos' : s.length === 1 ? _rotF(k, s[0]) : s.length + ' selecionados';
    return `<div class="fi2" data-fk="${k}"><span class="fl">${n}${novo ? '<span class="novo">novo</span>' : ''}</span>
      <button type="button" class="fb ${s ? 'ativo' : ''}" data-fabre="${k}" title="${esc(s ? s.map(v => _rotF(k, v)).join(' · ') : 'Todos')}"><span>${esc(rot)}</span><i>▾</i></button>
      ${ab === k ? `<div class="fpop"><input class="fbusca" data-fbusca="${k}" placeholder="Buscar…" value="${esc((window.__fbus || {})[k] || '')}">
        <div class="facoes"><a data-ftodos="${k}">marcar os da busca</a><a data-flimpa="${k}">limpar</a><a data-ffecha="1">fechar ✕</a></div><div class="flista">${_listaF(k)}</div></div>` : ''}</div>`; }).join('');
}
(function(){
  const css = document.createElement('style');
  css.textContent = `.fi2{position:relative;display:flex;flex-direction:column;gap:3px;font-size:12px;font-weight:600;color:#3a4a55}
  .fb{display:flex;justify-content:space-between;align-items:center;gap:6px;font:inherit;font-weight:500;font-size:13px;padding:6px 9px;border:1px solid #c9d3db;border-radius:8px;background:#f6f8fa;cursor:pointer;text-align:left;color:#1d2b33;min-width:0}
  .fb span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.fb.ativo{border-color:#1f4e79;background:#e3edf7;font-weight:700}.fb i{font-style:normal;color:#7b8790}
  .fpop{position:absolute;top:100%;left:0;z-index:50;margin-top:4px;width:max(100%,300px);background:#fff;border:1px solid #b9c7d3;border-radius:10px;box-shadow:0 10px 30px rgba(20,40,60,.22);padding:8px}
  .fbusca{width:100%;box-sizing:border-box;font:inherit;font-weight:400;padding:6px 8px;border:1px solid #c9d3db;border-radius:7px}
  .facoes{display:flex;gap:12px;margin:6px 2px;font-weight:600}.facoes a{color:#1f4e79;cursor:pointer;font-size:11.5px}.facoes a:last-child{margin-left:auto;color:#7b8790}
  .flista{max-height:260px;overflow:auto}.filtros label.fop,.fop{display:grid;flex-direction:row;text-align:left;font-size:12.5px;grid-template-columns:18px 1fr auto;gap:6px;align-items:center;padding:4px 4px;border-radius:6px;font-weight:400;cursor:pointer;color:#1d2b33}
  .fop span{text-align:left;overflow:hidden;text-overflow:ellipsis}.fop input{margin:0}.fop:hover{background:#f2f6f9}.fop.on{background:#e3edf7;font-weight:600}.fop em{font-style:normal;color:#7b8790;font-size:11px}.fmais{font-size:11px;color:#7b8790;margin:6px 4px;font-weight:400}`;
  document.head.appendChild(css);
  const reset = () => { if(typeof PAG === 'object') for(const p in PAG) PAG[p] = 0; };
  document.addEventListener('click', e => {
    const a = e.target.closest('[data-fabre]');
    if(a){ e.stopImmediatePropagation(); window.__fab = window.__fab === a.dataset.fabre ? null : a.dataset.fabre; desenharFiltros();
      const i = document.querySelector('.fbusca'); if(i) i.focus(); return; }
    if(e.target.closest('[data-ffecha]')){ e.stopImmediatePropagation(); window.__fab = null; desenharFiltros(); return; }
    const l = e.target.closest('[data-flimpa]'); if(l){ e.stopImmediatePropagation(); delete SEL[l.dataset.flimpa]; reset(); render(); return; }
    const t = e.target.closest('[data-ftodos]'); if(t){ e.stopImmediatePropagation(); const k = t.dataset.ftodos;
      document.querySelectorAll(`.fpop input[data-fop="${k}"]`).forEach(c => { if(!ehSel(k, c.value)) alternar(k, c.value); }); reset(); render(); return; }
    if(e.target.closest('.fpop')){ e.stopImmediatePropagation(); return; }
    if(window.__fab && !e.target.closest('.fi2')){ window.__fab = null; desenharFiltros(); }
  }, true);
  document.addEventListener('change', e => { const c = e.target.closest('[data-fop]'); if(!c) return; e.stopImmediatePropagation(); alternar(c.dataset.fop, c.value); reset(); render(); }, true);
  document.addEventListener('input', e => { const b = e.target.closest('[data-fbusca]'); if(!b) return; e.stopImmediatePropagation();
    (window.__fbus || (window.__fbus = {}))[b.dataset.fbusca] = b.value; const L = b.closest('.fpop').querySelector('.flista'); if(L) L.innerHTML = _listaF(b.dataset.fbusca); }, true);
})();

// ===================== impressão da ficha =====================
// Dentro do Google Sites o painel roda em quadros que bloqueiam a janela de impressão:
// a ficha abre numa aba própria (que imprime / salva em PDF); se a aba for bloqueada, baixa a ficha como HTML.
function imprimirFicha(el, titulo, paisagem){
  const c = el.cloneNode(true);
  c.querySelectorAll('details').forEach(d => d.open = true);
  c.querySelectorAll('.fa,.acoes,[data-fecha],[data-imp]').forEach(x => x.remove());
  // a linha de títulos da tabela se repete quando a tabela continua na página seguinte
  c.querySelectorAll('table').forEach(tb => { if(tb.tHead) return; const r = tb.querySelector('tr'); if(r && r.querySelector('th') && !r.querySelector('td')){ const th = tb.createTHead(); th.appendChild(r); } });
  // quadros: cada título de seção (.sb ou h3) e o que vem depois dele, até o próximo título, ficam numa caixa
  [...c.querySelectorAll('.sb, h3')].forEach(h => {
    if(h.parentElement && h.parentElement.classList.contains('qd')) return;
    const q = document.createElement('div'); q.className = 'qd'; h.parentNode.insertBefore(q, h);
    let x = h; while(x){ const prox = x.nextSibling; q.appendChild(x); x = prox; if(x && x.nodeType===1 && x.matches('.sb, h3')) break; }
  });
  const css = [...document.querySelectorAll('style')].map(x => x.textContent).join('\n');
  const html = `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>${String(titulo||'Ficha').replace(/</g,'')}</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&display=swap" rel="stylesheet"><style>${css}
@page{size:A4 ${paisagem ? 'landscape' : 'portrait'};margin:10mm}html,body{background:#fff!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}body{padding:12px;font-family:Barlow,Arial,sans-serif}
.fi,.ficha,.fo{box-shadow:none!important;max-width:980px;margin:0 auto!important;position:static!important}.rolar,.tw{overflow:visible!important;max-height:none!important}
.qd{border:1px solid #cfdcd3;border-radius:8px;margin:10px 0;overflow:hidden;background:#fff;-webkit-box-decoration-break:clone;box-decoration-break:clone}thead{display:table-header-group}tr{break-inside:avoid}.qd>.sb,.qd>h3{break-after:avoid}.qd>.sb,.qd>h3{background:#eef4ef!important;margin:0!important;padding:6px 10px!important;border:0!important;border-bottom:1px solid #cfdcd3!important;border-radius:0!important}.qd>:not(.sb):not(h3){margin-left:10px;margin-right:10px}.qd>:last-child{margin-bottom:8px}
details{border:1px solid #cfdcd3;border-radius:8px;margin:10px 0;overflow:hidden;-webkit-box-decoration-break:clone;box-decoration-break:clone}details>summary{background:#eef4ef;padding:6px 10px;border-bottom:1px solid #cfdcd3}details>:not(summary){margin-left:10px;margin-right:10px}
.moldura{position:fixed;top:0;left:0;right:0;bottom:0;border:1.5px solid #9fb8a8;border-radius:10px;pointer-events:none;z-index:0}
@media print{body{padding:14px 16px!important}.cx{grid-template-columns:repeat(5,1fr)!important}}
.wrap{max-width:none}body>#impressao{display:block!important}.aviso-imp{max-width:980px;margin:0 auto 10px;font:13px Arial,sans-serif;color:#444}@media print{.aviso-imp{display:none}body{padding:0}}</style></head>
<body><div class="moldura"></div><p class="aviso-imp">Na janela de impressão, escolha <b>Salvar como PDF</b> em "Destino".</p><div style="font:11px Arial,sans-serif;color:#5a6672;text-align:right;margin:0 auto 6px;max-width:980px">Extraído em ${new Date().toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'})} · Painel SDR 2026</div>${c.outerHTML}
<script>window.addEventListener('load',function(){setTimeout(function(){window.focus();window.print();},600);});<\/script></body></html>`;
  // no celular (ou dentro do Google Sites) o painel monta o PDF pronto, na orientação certa
  try{ const P = window.parent !== window && parent.__pdfEmbutido && parent.__pdfDireto; if(P) return P(html, titulo || 'ficha'); }catch(e){}
  let w = null; try{ w = window.open('', '_blank'); }catch(e){}
  if(w && w.document){ w.document.open(); w.document.write(html); w.document.close(); return; }
  try{ const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([html], {type:'text/html;charset=utf-8'}));
    a.download = String(titulo||'ficha').replace(/[^\w-]+/g,'_')+'.html'; document.body.appendChild(a); a.click(); a.remove(); }catch(e){ window.print(); }
}
