'use strict';
let all={events:[],demo:false}, event=null, selectedId=null, page='events', editPerson=null, editingEvent=false, lastDraw=null;
const $=(s)=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const cash=v=>(Number(v||0)/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const digits=n=>String(n).padStart(3,'0');
const dt=v=>{try{return v?new Date(v).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'}):'—'}catch(_){return v||'—'}};
const mdate=v=>v?String(v).split('-').reverse().join('/'):'Data não informada';
const badges={ACTIVE:'Ativo',VOID:'Cancelado',WINNER:'Premiado',REMOVED:'Retirado'};
const eventRef=()=>selectedId||event?.id;
function notify(msg,error=false,scroll=true){const el=$('#toast');el.textContent=msg;el.className='toast'+(error?' error':'');if(scroll)window.scrollTo({top:0,behavior:'smooth'});clearTimeout(notify.t);notify.t=setTimeout(()=>el.classList.add('hidden'),7000)}
async function api(path){const resp=await fetch(path,{cache:'no-store'});const data=await resp.json();if(!resp.ok)throw Error(data.error||'Falha ao carregar.');return data}
async function act(action,values={}){const r=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...values})});const d=await r.json();if(!r.ok)throw Error(d.error||'Operação não realizada.');return d}
async function load(){all=await api('/api/state');if(selectedId){try{event=await api('/api/event?event_id='+selectedId)}catch(_){selectedId=null;event=null;page='events'}}render()}
async function operate(action,values={}){try{const r=await act(action,values);if(r.event_id)selectedId=r.event_id;await load();notify(r.message||'Operação realizada.');return r}catch(ex){notify(ex.message,true);return null}}
function navigate(next){if(next!=='events'&&!event&&next!=='backup'){next='events'}page=next;editPerson=null;editingEvent=false;render();window.scrollTo({top:0,behavior:'smooth'})}
function title(){let labels={events:'Meus eventos',dashboard:'Visão geral',people:'Compradores',purchases:'Registro de compras',tickets:'Números da sorte',draw:'Sorteios',settings:'Configuração do evento',backup:'Backup e recuperação'};return labels[page]||'Mercamell PromoControl'}
function render(){
  $('#pageTitle').textContent=title();$('#eventBreadcrumb').textContent=event?('MERCAMELL • '+event.name.toUpperCase()):'MERCAMELL • TODOS OS EVENTOS';
  $('#modeFlag').textContent=all.demo?'MODO DE TESTE':'AMBIENTE REAL';
  $('#modeFlag').className='tag '+(all.demo?'tag-warning':'');
  $('#eventFlag').textContent=event?(event.archived?'ARQUIVADO':event.frozen?(event.winners.length===event.prizes.length?'CONCLUÍDO':'FECHADO'):'ABERTO'):'SEM EVENTO SELECIONADO';
  $('#eventFlag').className='tag '+(event?.archived?'tag-muted':event?.frozen?'tag-error':'');
  document.querySelectorAll('[data-page]').forEach(n=>n.classList.toggle('selected',n.dataset.page===page));
  const views={events:renderEvents,dashboard:renderDashboard,people:renderPeople,purchases:renderPurchases,tickets:renderTickets,draw:renderDraw,settings:renderSettings,backup:renderBackup};
  $('#content').innerHTML=(views[page]||renderEvents)();bindForms();if(page==='draw')syncDrawPreferences();
}
function metric(label,num,cls=''){return `<div class="metric"><span>${label}</span><strong class="${cls}">${num}</strong></div>`}
function eventForm(e=null){const tiers=e?.tiers||[{amount_cents:2500,tickets:1},{amount_cents:5000,tickets:2},{amount_cents:8000,tickets:3}];
  return `<form id="eventForm"><div class="formgrid">
  <div class="field"><label>Nome do evento *</label><input name="name" required maxlength="120" placeholder="Ex.: Reinauguração Kiruna" value="${esc(e?.name||'')}"></div>
  <div class="field"><label>Data (opcional)</label><input name="event_date" type="date" value="${esc(e?.event_date||'')}"></div>
  <div class="field full"><label>Descrição</label><textarea name="description" placeholder="Local, horário e observações">${esc(e?.description||'')}</textarea></div>
  <div class="field"><label>Faixas de compras (R$ = números), uma por linha *</label><textarea name="tiers" rows="5" required spellcheck="false">${tiers.map(x=>(x.amount_cents/100).toFixed(2).replace('.',',')+' = '+x.tickets).join('\n')}</textarea><span class="smalltxt">Ex.: 25 = 1, 50 = 2, 80 = 3. Somente antes da primeira compra.</span></div>
  <div class="field"><label>Prêmios, um por linha *</label><textarea name="prizes" rows="5" required>${esc((e?.prizes||['Air fryer','Sanduicheira','Abridor elétrico de vinho']).join('\n'))}</textarea><span class="smalltxt">A ordem das linhas define a sequência dos sorteios.</span></div>
  <div class="field full"><label>Marcas que dão bônus (separadas por vírgula)</label><input name="brands" value="${esc((e?.brands||['Honey Cake','Granuti','New York Slices','Vittai']).join(', '))}"></div>
  <div class="field"><label>Quantidade do bônus</label><input name="bonus_count" type="number" min="0" max="20" required value="${e?.bonus_count??1}"></div>
  <div class="field"><label>Máximo de números por pessoa</label><input name="max_tickets" type="number" min="1" max="100" required value="${e?.max_tickets??4}"></div>
  </div><div class="buttons"><button class="btn orange" type="submit">${e?'Salvar configurações':'Criar evento'}</button><button class="btn secondary" type="button" data-hide-event-form>Cancelar</button></div></form>`}
function renderEvents(){const list=all.events;
return `<div class="hero"><div><div class="orange-label">MERCAMELL PROMOCONTROL</div><h2>Um sistema para todos os seus eventos</h2><p class="subtitle">Cada evento possui seus compradores, compras sequenciais, regras e sorteios independentes.</p></div><button class="btn orange" data-new-event>+ Criar evento</button></div>
${editingEvent?`<div class="card"><h2>Novo evento</h2><p class="subtitle">Defina suas regras de compras, limite de números e prêmios.</p>${eventForm()}</div>`:''}
<div class="toolbar"><h2>Eventos cadastrados (${list.length})</h2></div>
${list.length?`<div class="grid3">${list.map(e=>`<div class="event-card ${e.archived?'archived':''}">
<div class="row between"><span class="tag ${e.archived?'tag-muted':e.frozen?'tag-error':''}">${e.archived?'ARQUIVADO':e.frozen?'FECHADO':'ABERTO'}</span><span class="smalltxt">ID ${e.id}</span></div>
<div><h3 class="event-name">${esc(e.name)}</h3><div class="event-meta">${mdate(e.event_date)} • ${e.people_count} compradores</div></div>
<div class="row between"><b>${cash(e.sales_cents)}</b><span class="smalltxt">${e.winner_count}/${e.prizes.length} prêmios</span></div>
<div class="event-actions"><button class="btn ${e.archived?'secondary':''}" data-open-event="${e.id}">Abrir evento</button><button class="btn secondary" data-duplicate-event="${e.id}" title="Criar novo evento com as mesmas regras">Duplicar</button></div></div>`).join('')}</div>`:'<div class="card empty">Nenhum evento cadastrado. Clique em Criar evento para começar.</div>'}`}
function renderDashboard(){const e=event;
return `<div class="hero"><div><div class="orange-label">EVENTO ${e.event_date?mdate(e.event_date):'SEM DATA DEFINIDA'}</div><h2>${esc(e.name)}</h2><p class="subtitle">${esc(e.description||'Acompanhe o cadastro, as compras e a apuração dos prêmios.')}</p></div><button class="btn orange" data-page="purchases">+ Nova compra</button></div>
<div class="grid4">${metric('Compradores',e.metrics.people)}${metric('Números disponíveis',e.metrics.active_tickets)}${metric('Compras válidas',e.metrics.sales_count)}${metric('Faturamento informado',cash(e.metrics.total_cents),'orange')}</div>
<div class="grid2" style="margin-top:18px"><div class="card"><h2>Regras deste evento</h2>${e.tiers.map(x=>`<div class="rule-row">A partir de ${cash(x.amount_cents)} <strong>${x.tickets} número(s)</strong></div>`).join('')}
<div class="rule-row">Bônus por marca participante <strong>+${e.bonus_count} número(s)</strong></div><div class="rule-row">Limite por comprador <strong>${e.max_tickets} número(s)</strong></div>
<p class="smalltxt">Bônus condicionado à primeira faixa e limitado a uma concessão por pessoa.</p><div class="buttons"><button class="btn secondary" data-page="settings">Configurações</button></div></div>
<div class="card"><h2>Próximos passos</h2><p class="subtitle">Fluxo recomendado para cada evento:</p>
<div class="rule-row">1. Cadastrar compradores <span>✓</span></div><div class="rule-row">2. Registrar compras (código automático) <span>→</span></div><div class="rule-row">3. Conferir números <span>→</span></div><div class="rule-row">4. Congelar e apurar <span>→</span></div>
<div class="buttons"><button class="btn" data-page="people">Compradores</button><button class="btn secondary" data-page="draw">Sorteio</button></div></div></div>`}
function renderPeople(){const e=event;const existing=editPerson?e.participants.find(p=>p.id===editPerson):null;
return `<div class="grid2"><div class="card"><h2>${existing?'Editar comprador':'Cadastrar comprador'}</h2><p class="subtitle">Cadastros exclusivos deste evento.</p>
${e.frozen?'<div class="note warn">Cadastros fechados. Reabra no painel de sorteio para editar.</div>':`<form id="personForm"><div class="formgrid">
<div class="field full"><label>Nome completo *</label><input name="name" required minlength="3" maxlength="100" value="${esc(existing?.name||'')}" placeholder="Nome do morador"></div>
<div class="field"><label>Telefone (opcional)</label><input name="phone" inputmode="numeric" maxlength="16" value="${esc(existing?.phone||'')}" placeholder="DDD + número"></div>
<div class="field"><label>Apartamento (opcional)</label><input name="apartment" maxlength="30" value="${esc(existing?.apartment||'')}" placeholder="Ex.: 82, Torre A"></div>
<div class="field full"><label>Observações (opcional)</label><textarea name="note">${esc(existing?.note||'')}</textarea></div></div>
<div class="buttons"><button class="btn" type="submit">${existing?'Salvar alterações':'Cadastrar comprador'}</button>${existing?'<button class="btn secondary" data-clear-person type="button">Cancelar edição</button>':''}</div></form>`}</div>
<div class="card"><h2>Controle de participantes</h2><div class="grid2">${metric('Cadastrados',e.metrics.people)}${metric('Com números',e.metrics.eligible)}</div><p class="subtitle" style="margin-top:12px">Compradores podem voltar e comprar novamente. O valor será somado automaticamente.</p><div class="note">O telefone ajuda a identificar pessoas com nomes semelhantes, mas não é obrigatório.</div></div></div>
<div class="card"><div class="toolbar"><h2>Compradores (${e.participants.length})</h2><input class="search" id="personSearch" placeholder="Buscar por nome ou telefone" style="max-width:290px"></div>
<div class="tablewrap"><table><thead><tr><th>Nome</th><th>Apartamento</th><th>Telefone</th><th>Compras</th><th>Números ativos</th><th>Ação</th></tr></thead><tbody id="peopleRows">${e.participants.length?e.participants.map(p=>`<tr data-search="${esc((p.name+' '+p.phone+' '+p.apartment).toLowerCase())}"><td><b>${esc(p.name)}</b><br><span class="smalltxt">ID ${p.id}</span></td><td>${esc(p.apartment||'—')}</td><td>${esc(p.phone||'—')}</td><td>${cash(p.spent_cents)}</td><td>${p.numbers.filter(n=>n.status==='ACTIVE').length}</td><td>${e.frozen?'—':`<button class="btn secondary sm" data-edit-person="${p.id}">Editar</button> <button class="btn sm" data-buy-for="${p.id}">Compra</button>`}</td></tr>`).join(''):'<tr><td colspan="6" class="empty">Nenhum comprador cadastrado.</td></tr>'}</tbody></table></div></div>`}
function renderPurchases(){const e=event;const options=e.participants.map(p=>`<option value="${p.id}" ${window.purchasePerson===p.id?'selected':''}>${esc(p.name)} — ID ${p.id}</option>`).join('');
return `<div class="grid2"><div class="card"><h2>Nova compra</h2><p class="subtitle">O código da compra é automático, sequencial e exclusivo deste evento. Ex.: ${String(e.id).padStart(3,'0')}-000001.</p>
${e.frozen?'<div class="note warn">Cadastros bloqueados. Cancele a apuração e reabra o evento para registrar novas compras.</div>':!e.participants.length?'<div class="note warn">Cadastre um comprador antes de lançar compras.</div><div class="buttons"><button class="btn" data-page="people">Cadastrar comprador</button></div>':
`<form id="purchaseForm"><div class="formgrid">
<div class="field full"><label>Comprador *</label><select name="participant_id" required><option value="">Selecione um comprador</option>${options}</select></div>
<div class="field"><label>Valor da compra (R$) *</label><input name="amount" inputmode="decimal" required placeholder="Ex.: 28,90"></div>
<div class="field"><label>ID externo da transação (opcional)</label><input name="transaction_id" maxlength="100" autocomplete="off" placeholder="Pode deixar em branco"><span class="smalltxt">O sistema gera o código da compra automaticamente. Use o ID externo só se precisar conciliar pagamentos.</span></div>
<div class="field full"><label>Comprou algum produto participante?</label><div class="checkgrid">${e.brands.map(b=>`<label class="check"><input type="checkbox" name="brand" value="${esc(b)}">${esc(b)}</label>`).join('')||'<span class="smalltxt">Nenhuma marca configurada.</span>'}</div></div></div>
<div class="buttons"><button class="btn orange" type="submit">Registrar compra e calcular números</button></div></form>`}</div>
<div class="card"><h2>Resumo do evento</h2><div class="grid2">${metric('Compras válidas',e.metrics.sales_count)}${metric('Faturamento',cash(e.metrics.total_cents))}</div><div class="note" style="margin-top:16px">Compras de uma mesma pessoa são acumuladas. O bônus por degustação é concedido no máximo uma vez por pessoa, respeitando o limite do evento.</div><div class="buttons"><button class="btn secondary" data-page="tickets">Conferir números</button></div></div></div>
<div class="card"><div class="toolbar"><h2>Histórico de compras</h2><span class="smalltxt">As compras estornadas permanecem no histórico.</span></div>
<div class="tablewrap"><table><thead><tr><th>Data</th><th>Comprador</th><th>Código da compra</th><th>ID externo</th><th>Valor</th><th>Marcas</th><th>Status</th><th></th></tr></thead><tbody>
${e.purchases.length?e.purchases.map(p=>`<tr><td>${dt(p.created_at)}</td><td>${esc(p.name)}</td><td><b>${esc(p.purchase_code)}</b></td><td>${esc(p.transaction_id||'—')}</td><td>${cash(p.amount_cents)}</td><td>${esc(p.brands.join(', ')||'—')}</td><td><span class="tag ${p.voided_at?'tag-error':''}">${p.voided_at?'ESTORNADA':'VÁLIDA'}</span></td><td>${!p.voided_at&&!e.frozen?`<button class="btn secondary sm" data-void-purchase="${p.id}">Estornar</button>`:''}</td></tr>`).join(''):'<tr><td class="empty" colspan="8">Nenhuma compra registrada.</td></tr>'}</tbody></table></div></div>`}
function renderTickets(){const e=event;return `<div class="card"><div class="toolbar"><div><h2>Números da sorte</h2><p class="subtitle mb0">Sequência exclusiva deste evento. Números cancelados nunca são reutilizados.</p></div><a class="btn secondary" href="/api/export.csv?event_id=${e.id}">Exportar CSV</a></div>
<div class="note">O sorteio considera somente números ativos. Os números de uma pessoa vencedora deixam de concorrer aos demais prêmios.</div><div style="height:15px"></div>
<div class="tablewrap"><table><thead><tr><th>Comprador</th><th>Apto.</th><th>Compras acumuladas</th><th>Bônus</th><th>Números e situação</th></tr></thead><tbody>
${e.participants.filter(p=>p.numbers.length).map(p=>`<tr><td><b>${esc(p.name)}</b></td><td>${esc(p.apartment||'—')}</td><td>${cash(p.spent_cents)}</td><td>${p.qualifying_brand?'Sim':'Não'}</td><td>${p.numbers.map(n=>`<span class="num ${n.status.toLowerCase()}" title="${badges[n.status]||n.status}">${digits(n.number)}</span>`).join('')}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">Nenhum número emitido.</td></tr>'}</tbody></table></div>
<p class="smalltxt">Verde: disponível; verde claro: premiado; cinza: retirado após prêmio; vermelho: cancelado por estorno.</p></div>`}
function renderDraw(){
 const e=event, count=e.winners.length, allDone=count>=e.prizes.length;
 const pend=e.pending_draw, next=e.prizes[count];
 const canClose=e.metrics.eligible>=e.prizes.length;
 return `<div class="card"><div class="toolbar"><div><h2>Sorteios — ${esc(e.name)}</h2><p class="subtitle mb0">Um prêmio por pessoa • resultados exibidos em tela cheia e confirmados manualmente.</p></div><span class="tag ${e.frozen?'tag-error':''}">${e.frozen?'CADASTRO FECHADO':'CADASTRO ABERTO'}</span></div>
 <div class="grid3">${e.prizes.map((p,i)=>{let w=e.winners.find(w=>w.prize_order===i+1);return `<div class="prize ${!w&&i===count?'next':''}"><small>${i+1}º PRÊMIO</small>${e.prize_images?.[i+1]?`<img class="prize-photo" src="${esc(e.prize_images[i+1])}" alt="Foto do prêmio ${esc(p)}">`:''}<h3>${esc(p)}</h3><div class="winner">${w?`${esc(w.name)}<br>Apartamento ${esc(w.apartment||'não informado')}<br>Número ${digits(w.number)}`:i===count?pend?'Resultado pendente de confirmação':'Próximo prêmio':'Aguardando'}</div></div>`}).join('')}</div>
 ${!e.frozen?`<div class="note warn" style="margin-top:16px">Confira todas as compras e números. Salve um backup antes de encerrar o cadastro.</div><div class="buttons"><button class="btn orange" data-action="freeze" ${canClose?'':'disabled'}>Encerrar cadastro e congelar números</button><button class="btn secondary" data-page="tickets">Conferir números</button><a class="btn secondary" href="/api/backup">Baixar backup</a></div>${!canClose?`<p class="smalltxt">É necessário ter ao menos ${e.prizes.length} participantes elegíveis para os ${e.prizes.length} prêmios.</p>`:''}`:
 `<div class="draw-studio" style="margin-top:17px">
 <div class="orange-label">${allDone?'APURAÇÃO CONCLUÍDA':pend?'AGUARDANDO SUA DECISÃO':`PRÊMIO ${count+1} DE ${e.prizes.length}`}</div>
 <h2>${allDone?'Os prêmios foram confirmados':esc(next)}</h2>
 <p>${allDone?'Todos os ganhadores podem ser exibidos e exportados em uma imagem.':pend?'Há um número selecionado. Confirme o morador ou realize um novo sorteio.':'Configure a contagem e o som antes de iniciar o próximo sorteio.'}</p>
 ${!allDone&&!pend?`<div class="draw-controls"><div class="field"><label for="countdownSeconds">Contagem regressiva</label><select id="countdownSeconds"><option value="0">Sem contagem</option><option value="3">3 segundos</option><option value="5">5 segundos</option><option value="10">10 segundos</option><option value="15">15 segundos</option></select></div><div class="field"><label for="soundMode">Som do sorteio</label><select id="soundMode"><option value="off">Sem som</option><option value="beep">Bipes na contagem</option><option value="celebrate">Bipes + som de celebração</option></select></div></div>`:''}
 <div class="recording-controls"><div class="recording-text"><strong id="recordingState">${recordingActive()?'● Gravação em andamento':'Vídeo do sorteio (opcional)'}</strong><span>Compartilhe esta aba do navegador para gravar do início ao fim. O vídeo será salvo no computador em WebM.</span></div><button class="btn secondary" data-record-start ${recordingActive()?'disabled':''}>● Iniciar gravação</button><button class="btn secondary" data-record-stop ${recordingActive()?'':'disabled'}>■ Finalizar e salvar vídeo</button></div>
 <div class="buttons">${allDone?'<button class="btn orange large" data-draw-summary>★ Ver ganhadores e exportar imagem</button>':pend?'<button class="btn orange large" data-draw-show>Ver resultado pendente</button>':'<button class="btn orange large" data-draw-start>★ Iniciar sorteio</button>'}<button class="btn danger" data-cancel-draw>↶ ${count||pend?'Cancelar apuração e reabrir':'Reabrir cadastro'}</button><a class="btn secondary" href="/api/backup">Baixar backup</a></div>
 </div>`}
 </div>
 ${count?`<div class="card"><h2>Ganhadores confirmados (${count})</h2>${e.winners.map(w=>`<div class="rule-row"><span>${esc(w.prize)}</span><strong>Nº ${digits(w.number)} — ${esc(w.name)} • Apto. ${esc(w.apartment||'não informado')}</strong></div>`).join('')}</div>`:''}
 ${e.attempts?.some(x=>x.status==='DECLINED')?`<div class="card"><h2>Resultados recusados por ausência</h2><p class="smalltxt">Estes números não voltam a participar desta apuração. Reabrir o evento reinicia a apuração, preservando compras.</p>${e.attempts.filter(a=>a.status==='DECLINED').map(a=>`<div class="rule-row"><span>${esc(a.prize)} — Nº ${digits(a.number)}</span><strong>${esc(a.name)}</strong></div>`).join('')}</div>`:''}
 <div class="note warn"><b>Apuração:</b> a seleção aleatória local deve ser utilizada somente quando compatível com o regulamento autorizado. Se o morador ausente for retirado, a tentativa é registrada; ao confirmar um ganhador, ele não participa dos demais prêmios.</div>
 ${e.frozen?`<div class="note danger" style="margin-top:12px"><b>Cancelar e reabrir:</b> anula resultados e tentativas, mas mantém cadastros, apartamentos, compras e números. Não use depois de entregar os prêmios.</div>`:''}`
}
function renderSettings(){const e=event;const purchaseCount=e.purchases.length;return `<div class="card"><div class="toolbar"><h2>Configurações de ${esc(e.name)}</h2><button class="btn secondary" data-page="events">Voltar aos eventos</button></div>
<div class="note ${purchaseCount?'warn':''}">${purchaseCount?'Já existem compras neste evento: faixas, marcas, bônus e limite estão protegidos contra alteração para não afetar números emitidos. Prêmios e informações gerais podem ser editados antes da apuração.':'As regras de participação poderão ser alteradas até a primeira compra.'}</div><div style="height:15px"></div>
${e.frozen?'<div class="note warn">Evento fechado. Reabra-o na tela de sorteios antes de editar.</div>':eventForm(e)}</div>
<div class="card"><h2>Fotos dos prêmios</h2><p class="subtitle">Você escolhe uma foto JPG/PNG por prêmio. As imagens aparecem no sorteio e no PNG final, ficam no banco local e acompanham o backup. As fotos são opcionais.</p>
<div class="prize-upload-grid">${e.prizes.map((name,i)=>`<div class="prize-upload-card"><div><b>${i+1}º prêmio — ${esc(name)}</b></div>${e.prize_images?.[i+1]?`<img class="prize-upload-preview" src="${esc(e.prize_images[i+1])}" alt="Foto do prêmio ${esc(name)}">`:'<div class="prize-photo-empty">Sem imagem</div>'}${e.frozen?'<p class="smalltxt">Reabra o evento para editar.</p>':`<div class="field"><label for="prizeImage${i+1}">Escolher foto JPG/PNG</label><input type="file" id="prizeImage${i+1}" data-prize-upload="${i+1}" accept="image/jpeg,image/png"></div>${e.prize_images?.[i+1]?`<button type="button" class="btn secondary sm" data-prize-remove="${i+1}">Remover foto</button>`:''}`}</div>`).join('')}</div><p class="smalltxt">Dica: se você alterar o nome ou a posição de um prêmio, confira a foto novamente.</p></div>
<div class="card"><h2>Gerenciar evento</h2><p class="subtitle">Você pode arquivar eventos antigos sem apagar seus dados.</p><div class="buttons"><button class="btn secondary" data-duplicate-event="${e.id}">Duplicar regras para novo evento</button><button class="btn secondary" data-archive-event="${e.id}">${e.archived?'Reativar evento':'Arquivar evento'}</button></div></div>`}
function renderBackup(){return `<div class="grid2"><div class="card"><h2>Backup completo</h2><p class="subtitle">Inclui todos os eventos, participantes, compras, números, resultados e histórico de alterações deste ambiente (${all.demo?'teste':'real'}).</p>
<a class="btn orange" href="/api/backup">Baixar backup completo (.json)</a><p class="smalltxt">Salve também em pendrive ou pasta externa. Ao atualizar o programa, mantenha o arquivo de dados ou restaure seu backup.</p></div>
<div class="card"><h2>Restaurar backup</h2><p class="subtitle">A recuperação substitui TODOS os dados locais deste ambiente pelo conteúdo do arquivo selecionado.</p>
<form id="restoreForm"><div class="field"><label>Selecionar backup das versões 2, 3 ou 4 (.json)</label><input id="backupFile" type="file" accept=".json,application/json" required></div><div class="field" style="margin-top:12px"><label>Digite RESTAURAR para confirmar</label><input id="restoreText" placeholder="RESTAURAR" required></div><div class="buttons"><button class="btn danger" type="submit">Restaurar base</button></div></form></div></div>
<div class="card"><h2>Importar cadastros da versão 1 (Market4u Kiruna)</h2><p class="subtitle">Se você já utilizou a versão anterior, importe o backup JSON dela. Todos os compradores, compras e números serão copiados para um NOVO evento, sem apagar os eventos desta versão.</p>
<form id="importV1Form"><div class="formgrid"><div class="field"><label>Nome do evento importado</label><input id="importName" value="Reinauguração Kiruna (importado v1)" required minlength="3"></div><div class="field"><label>Backup JSON exportado da v1</label><input id="importV1File" type="file" accept=".json,application/json" required></div></div><div class="buttons"><button class="btn secondary" type="submit">Importar backup da v1</button></div></form></div>
<div class="card"><h2>Armazenamento local</h2><p>Arquivo de banco de dados: <code>dados/${all.demo?'mercamell_demo.db':'mercamell_promocontrol.db'}</code></p><div class="note">Demonstração e operação real utilizam arquivos diferentes. O sistema não envia cadastros para a internet.</div></div>`}
function parseEventForm(form){const fd=new FormData(form);
 const tiers=String(fd.get('tiers')).trim().split(/\n+/).map(x=>{const parts=x.trim().match(/^\s*(\d+(?:[,.]\d{1,2})?)\s*(?:=|:|;)\s*(\d+)\s*$/);if(!parts)throw Error('Formato inválido de faixa: '+x+'. Use 25 = 1');return {amount_cents:Math.round(Number(parts[1].replace(',','.'))*100),tickets:Number(parts[2])}});
 return {name:String(fd.get('name')).trim(),event_date:String(fd.get('event_date')||''),description:String(fd.get('description')||''),tiers,
  prizes:String(fd.get('prizes')||'').split(/\n+/).map(x=>x.trim()).filter(Boolean),brands:String(fd.get('brands')||'').split(',').map(x=>x.trim()).filter(Boolean),bonus_count:Number(fd.get('bonus_count')),max_tickets:Number(fd.get('max_tickets'))};}
function bindForms(){
const eventFormEl=$('#eventForm');if(eventFormEl)eventFormEl.addEventListener('submit',async(ev)=>{ev.preventDefault();try{const data=parseEventForm(eventFormEl);const isEdit=page==='settings';const r=await operate(isEdit?'edit_event':'create_event',{...data,...isEdit?{event_id:event.id}:{}});if(r){editingEvent=false;await load();navigate(isEdit?'settings':'dashboard')}}catch(ex){notify(ex.message,true)}});
const formPerson=$('#personForm');if(formPerson)formPerson.addEventListener('submit',async(ev)=>{ev.preventDefault();const fd=new FormData(formPerson);const isEdit=!!editPerson;const r=await operate(isEdit?'edit_person':'add_person',{event_id:event.id,name:fd.get('name'),phone:fd.get('phone'),apartment:fd.get('apartment'),note:fd.get('note'),...isEdit?{participant_id:editPerson}:{}});if(r){if(!isEdit){window.purchasePerson=r.participant_id;navigate('purchases')}else{editPerson=null;render()}}});
const formBuy=$('#purchaseForm');if(formBuy)formBuy.addEventListener('submit',async(ev)=>{ev.preventDefault();const fd=new FormData(formBuy);const pid=Number(fd.get('participant_id'));const r=await operate('add_purchase',{event_id:event.id,participant_id:pid,amount:fd.get('amount'),transaction_id:fd.get('transaction_id'),brands:fd.getAll('brand')});if(r){window.purchasePerson=pid;render()}});
const formRestore=$('#restoreForm');if(formRestore)formRestore.addEventListener('submit',async(ev)=>{ev.preventDefault();if($('#restoreText').value!=='RESTAURAR'){notify('Digite RESTAURAR em maiúsculas.',true);return}if(!confirm('ATENÇÃO: substituir TODOS os eventos e cadastros desta base?'))return;try{const file=$('#backupFile').files[0];if(!file)return;const b=JSON.parse(await file.text());const r=await operate('restore',{backup:b});if(r){event=null;selectedId=null;lastDraw=null;navigate('events')}}catch(ex){notify('Erro no arquivo de backup: '+ex.message,true)}});
const importForm=$('#importV1Form');if(importForm)importForm.addEventListener('submit',async ev=>{ev.preventDefault();try{const f=$('#importV1File').files[0];if(!f)return;if(!confirm('Importar dados da v1 como um NOVO evento, preservando os atuais?'))return;const b=JSON.parse(await f.text());const r=await operate('import_v1',{backup:b,name:$('#importName').value});if(r){lastDraw=null;navigate('dashboard')}}catch(ex){notify('Erro de importação: '+ex.message,true)}});
const search=$('#personSearch');if(search)search.addEventListener('input',()=>{const val=search.value.trim().toLowerCase();document.querySelectorAll('#peopleRows tr[data-search]').forEach(tr=>{tr.hidden=!tr.dataset.search.includes(val)})});
}
document.addEventListener('change',async ev=>{
 const input=ev.target.closest('[data-prize-upload]');if(!input||!input.files?.length)return;
 const file=input.files[0],order=Number(input.dataset.prizeUpload);
 try{
  input.disabled=true;
  const data_url=await compressPrizeImage(file);
  const result=await operate('set_prize_image',{event_id:event.id,prize_order:order,data_url});
  if(result)notify('Imagem do '+order+'º prêmio salva.');
 }catch(ex){notify('Não foi possível salvar a imagem: '+ex.message,true)}finally{if(input.isConnected)input.disabled=false}
});
document.addEventListener('click',async(ev)=>{
 const remove=ev.target.closest('[data-prize-remove]');
 if(remove){if(confirm('Remover imagem deste prêmio?'))await operate('set_prize_image',{event_id:event.id,prize_order:Number(remove.dataset.prizeRemove),data_url:null});return}
 const go=ev.target.closest('[data-page]');if(go){navigate(go.dataset.page);return}
 const newEvent=ev.target.closest('[data-new-event]');if(newEvent){editingEvent=true;page='events';render();return}
 if(ev.target.closest('[data-hide-event-form]')){editingEvent=false;render();return}
 const open=ev.target.closest('[data-open-event]');if(open){selectedId=Number(open.dataset.openEvent);lastDraw=null;await load();navigate('dashboard');return}
 const duplicate=ev.target.closest('[data-duplicate-event]');if(duplicate){const e=all.events.find(x=>x.id===Number(duplicate.dataset.duplicateEvent));if(!e)return;const name=prompt('Nome do novo evento (somente regras e prêmios serão copiados):',e.name+' — Cópia');if(!name)return;const r=await operate('duplicate_event',{event_id:e.id,name});if(r){lastDraw=null;navigate('dashboard')}return}
 const archive=ev.target.closest('[data-archive-event]');if(archive){const e=all.events.find(x=>x.id===Number(archive.dataset.archiveEvent));if(e&&confirm((e.archived?'Reativar':'Arquivar')+' este evento sem perder seus cadastros?'))await operate('archive_event',{event_id:e.id});return}
 if(ev.target.closest('[data-clear-person]')){editPerson=null;render();return}
 const edit=ev.target.closest('[data-edit-person]');if(edit){editPerson=Number(edit.dataset.editPerson);render();window.scrollTo({top:0,behavior:'smooth'});return}
 const buy=ev.target.closest('[data-buy-for]');if(buy){window.purchasePerson=Number(buy.dataset.buyFor);navigate('purchases');return}
 const voidButton=ev.target.closest('[data-void-purchase]');if(voidButton){if(confirm('Estornar esta compra? Ela ficará no histórico, mas deixará de contar para a promoção. Números excedentes serão cancelados.'))await operate('void_purchase',{event_id:event.id,purchase_id:Number(voidButton.dataset.voidPurchase)});return}
 const cancel=ev.target.closest('[data-cancel-draw]');if(cancel){const winners=event.winners.length;const text=(winners||event.attempts?.length)?'CANCELAR':'REABRIR';const a=prompt(winners||event.attempts?.length?`Atenção: anulará ${winners} resultado(s) de sorteio e tentativas pendentes/recusadas. TODOS os compradores e compras serão PRESERVADOS. Digite CANCELAR para confirmar:`:'Nenhum prêmio foi sorteado. Digite REABRIR para liberar os cadastros:');if(a!==text){if(a!==null)notify('Confirmação incorreta. Nada foi alterado.',true);return}const action=(winners||event.attempts?.length)?'cancel_draw_reopen':'reopen';const r=await operate(action,{event_id:event.id});if(r)lastDraw=null;return}
 const action=ev.target.closest('[data-action]');if(action){const name=action.dataset.action;if(name==='freeze'&&!confirm('Encerrar compras e congelar os números deste evento? Os cadastros e compras serão preservados.'))return;const r=await operate(name,{event_id:event.id});if(r?.winner)lastDraw=r.winner;return}
});
document.addEventListener('click',async ev=>{
 if(ev.target.closest('[data-record-start]')){startDrawRecording();return}
 if(ev.target.closest('[data-record-stop]')){stopDrawRecording();return}
 if(ev.target.closest('[data-draw-start]')){await beginDraw(false);return}
 if(ev.target.closest('[data-draw-show]')){showDrawResult();return}
 if(ev.target.closest('[data-draw-summary]')){showSummary();return}
 if(ev.target.closest('[data-draw-redraw]')){await beginDraw(true);return}
 if(ev.target.closest('[data-draw-confirm]')){await confirmDraw();return}
 if(ev.target.closest('[data-draw-next]')){closeDrawModal();navigate('draw');return}
 if(ev.target.closest('[data-draw-final]')){showSummary();return}
 if(ev.target.closest('[data-draw-export]')){await exportResultsPNG();return}
 if(ev.target.closest('[data-draw-close]')){closeDrawModal();return}
});
document.addEventListener('change',ev=>{if(ev.target.matches('#countdownSeconds,#soundMode'))saveDrawPreferences()});
load().catch(ex=>notify('Não foi possível abrir o sistema: '+ex.message,true));

async function compressPrizeImage(file){
 if(!file)throw Error('Selecione uma foto.');
 if(!['image/jpeg','image/png'].includes(file.type))throw Error('Formato não suportado. Selecione um JPG ou PNG verdadeiro. Fotos HEIC/WEBP precisam ser convertidas antes.');
 if(!file.size)throw Error('O arquivo está vazio. Escolha outra imagem.');
 if(file.size>16_000_000)throw Error('Selecione uma foto com até 16 MB.');
 let img=null;
 try{
  // Prefira o decodificador nativo; ele não depende do carregamento de uma URL temporária.
  if(typeof createImageBitmap==='function'){
   try{img=await createImageBitmap(file)}catch(_){/* Tenta o carregamento tradicional abaixo. */}
  }
  if(!img){
   const url=URL.createObjectURL(file);
   try{
    img=await new Promise((resolve,reject)=>{
     const element=new Image();
     // Os eventos precisam ser registrados ANTES de informar a origem da imagem.
     element.onload=()=>resolve(element);
     element.onerror=()=>reject(Error('O navegador não conseguiu decodificar este arquivo.'));
     element.src=url;
    });
   }finally{URL.revokeObjectURL(url)}
  }
  const width=img.width||img.naturalWidth, height=img.height||img.naturalHeight;
  if(!width||!height)throw Error('A imagem não possui dimensões válidas.');
  const scale=Math.min(1,900/width,700/height);
  const c=document.createElement('canvas');c.width=Math.max(1,Math.round(width*scale));c.height=Math.max(1,Math.round(height*scale));
  const ctx=c.getContext('2d');
  if(!ctx)throw Error('Não foi possível preparar a imagem no navegador.');
  ctx.fillStyle='#ffffff';ctx.fillRect(0,0,c.width,c.height);
  ctx.drawImage(img,0,0,c.width,c.height);
  for(const quality of [.85,.72,.58,.4]){
   const data_url=c.toDataURL('image/jpeg',quality);
   if((data_url.length-23)*.75<=500000)return data_url;
  }
  throw Error('Imagem ficou muito grande mesmo após compactação. Use uma foto menor.');
 }catch(ex){
  if(/decodificar|dimensões válidas|decode|image format/i.test(String(ex.message))){
   throw Error('O arquivo selecionado não pôde ser aberto como JPG ou PNG. Abra a foto no Paint, use “Salvar como” → JPEG ou PNG e tente novamente.');
  }
  throw ex;
 }finally{
  if(img&&typeof img.close==='function')img.close();
 }
}