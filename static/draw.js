'use strict';
/* Mercamell PromoControl v3 — sorteio ao vivo, sem dependências externas. */
let drawBusy=false;
let audioContext=null;
const prefsKey='mercamell-promocontrol-draw-preferences';
function drawPrefs(){
 try{const saved=JSON.parse(localStorage.getItem(prefsKey)||'{}');return {
  seconds:[0,3,5,10,15].includes(Number(saved.seconds))?Number(saved.seconds):5,
  sound:['off','beep','celebrate'].includes(saved.sound)?saved.sound:'celebrate'};
 }catch(_){return {seconds:5,sound:'celebrate'}}
}
function syncDrawPreferences(){const p=drawPrefs();const secs=document.querySelector('#countdownSeconds');const snd=document.querySelector('#soundMode');if(secs)secs.value=String(p.seconds);if(snd)snd.value=p.sound}
function saveDrawPreferences(){const secs=document.querySelector('#countdownSeconds');const snd=document.querySelector('#soundMode');if(secs&&snd){try{localStorage.setItem(prefsKey,JSON.stringify({seconds:Number(secs.value),sound:snd.value}))}catch(_){/* Preferências não disponíveis neste navegador. */}}}
function drawOverlay(html){const root=document.querySelector('#drawModal');root.innerHTML=html;root.classList.remove('hidden');document.body.classList.add('modal-open')}
function closeDrawModal(){if(drawBusy)return;document.querySelector('#drawModal').classList.add('hidden');document.querySelector('#drawModal').innerHTML='';document.body.classList.remove('modal-open')}
function beep(frequency=580,duration=.12,volume=.09){
 if(!audioContext)return;
 try{const o=audioContext.createOscillator(),g=audioContext.createGain();o.type='sine';o.frequency.value=frequency;g.gain.setValueAtTime(volume,audioContext.currentTime);g.gain.exponentialRampToValueAtTime(.0001,audioContext.currentTime+duration);o.connect(g);g.connect(audioContext.destination);o.start();o.stop(audioContext.currentTime+duration)}catch(_){}
}
async function unlockAudio(sound){
 if(sound==='off')return;
 const Audio=window.AudioContext||window.webkitAudioContext;
 if(!Audio)return;
 try{audioContext=audioContext||new Audio();if(audioContext.state==='suspended')await audioContext.resume()}catch(_){audioContext=null}
}
function drawTick(sec,sound){if(sound==='off')return;beep(sec===1?780:480,.13,.07)}
function drawnSound(sound){if(sound!=='celebrate')return;[540,675,820].forEach((f,i)=>setTimeout(()=>beep(f,.2,.12),i*135))}
function modalFrame(label,title,body,actions){return `<div class="draw-dialog"><div class="draw-dialog-head"><div class="draw-brand"><img src="/static/mercamell-logo.png" alt="Mercamell"><div><strong>Promo<span>Control</span></strong><small>${esc(event?.name||'')}</small></div></div><div class="draw-modal-mode">${all.demo?'MODO DE TESTE':'SORTEIO DO EVENTO'}</div></div>
 <div class="draw-dialog-body"><div class="draw-tagline">${label}</div><h2>${title}</h2>${body}</div><div class="draw-dialog-actions">${actions}</div></div>`}
function loadingView(prize,secs){drawOverlay(modalFrame('O GRANDE MOMENTO',esc(prize),`<p class="modal-subtitle">Preparando o resultado...</p><div class="countdown-circle" id="countdownValue" aria-live="polite">${secs||'★'}</div><p class="modal-subtitle" id="countdownCaption">${secs?'O sorteio começa em instantes':'Selecionando um número...'}</p>`,`<span class="smalltxt">Aguarde a conclusão da seleção.</span>`))}
async function beginDraw(isRedraw){
 if(drawBusy||!event?.frozen||event.winners.length>=event.prizes.length)return;
 if(isRedraw&&!event.pending_draw)return;
 if(!isRedraw&&event.pending_draw){showDrawResult();return}
 if(isRedraw&&!confirm('O número atual será registrado como recusado por ausência e não poderá concorrer novamente nesta apuração. Deseja sortear outro número para este prêmio?'))return;
 drawBusy=true;
 const eId=event.id;
 const prize=event.prizes[event.winners.length];
 const p=drawPrefs();
 const secs=p.seconds;
 try{
  await unlockAudio(p.sound);
  loadingView(prize,secs);
  if(secs){for(let t=secs;t>0;t--){const element=document.querySelector('#countdownValue');if(element)element.textContent=String(t);drawTick(t,p.sound);await new Promise(r=>setTimeout(r,1000))}}
  const element=document.querySelector('#countdownValue');if(element)element.textContent='★';
  const caption=document.querySelector('#countdownCaption');if(caption)caption.textContent='Selecionando o número...';
  const r=await act(isRedraw?'redraw':'draw',{event_id:eId});
  await load();drawnSound(p.sound);
  showDrawResult();
 }catch(ex){document.querySelector('#drawModal').classList.add('hidden');document.body.classList.remove('modal-open');notify(ex.message,true)}
 finally{drawBusy=false}
}
function showDrawResult(){
 const p=event?.pending_draw;if(!p)return;
 const name=esc(p.name),apto=p.apartment?`<div class="winner-apartment">Apartamento ${esc(p.apartment)}</div>`:'';
 drawOverlay(modalFrame(`PRÊMIO ${p.prize_order} DE ${event.prizes.length}`,esc(p.prize),`<p class="modal-subtitle">Número selecionado</p><div class="result-number">${digits(p.number)}</div><div class="draw-result-owner">${name}</div>${apto}<p class="draw-result-help">Confirme o ganhador ou realize um novo sorteio se estiver ausente.</p>`,`<button class="btn secondary large" data-draw-redraw>↻ Resortear este prêmio</button><button class="btn orange large" data-draw-confirm>✓ Confirmar ganhador</button><button class="btn secondary" data-draw-close>Fechar tela</button>`))
}
async function confirmDraw(){
 if(drawBusy||!event?.pending_draw)return;drawBusy=true;
 const p=event.pending_draw;
 try{
  await act('confirm_draw',{event_id:event.id});
  await load();
  const final=event.winners.length>=event.prizes.length;
  drawOverlay(modalFrame('GANHADOR CONFIRMADO',esc(p.prize),`<div class="result-number">${digits(p.number)}</div><div class="draw-result-owner">${esc(p.name)}</div><p class="modal-subtitle">Resultado salvo com sucesso.</p>`,final?`<button class="btn orange large" data-draw-final>★ Avançar para os 3 ganhadores</button>`:`<button class="btn orange large" data-draw-next>→ Prosseguir para o próximo prêmio</button>`))
 }catch(ex){notify(ex.message,true)}finally{drawBusy=false}
}
function showSummary(){
 if(!event||event.winners.length!==event.prizes.length)return;
 drawOverlay(modalFrame('RESULTADO FINAL','Parabéns aos ganhadores!',`<p class="modal-subtitle">${esc(event.name)}${event.event_date?' • '+esc(mdate(event.event_date)):''}</p><div class="winner-summary-grid">${event.winners.map((w,i)=>`<div class="winner-summary-row"><div class="winner-rank">${i+1}º</div><div class="winner-info"><small>${esc(w.prize)}</small><strong>${esc(w.name)}</strong><span>Número ${digits(w.number)}</span></div></div>`).join('')}</div><p class="summary-hint">A imagem compartilhável inclui apenas o nome, número e prêmio de cada ganhador; não inclui apartamento, telefone ou dados de compras.</p>`,`<button class="btn orange large" data-draw-export>↓ Exportar imagem PNG</button><button class="btn secondary large" data-draw-close>Fechar</button>`))
}
function canvasRounded(ctx,x,y,w,h,r){ctx.beginPath();ctx.roundRect(x,y,w,h,r)}
function textFitted(ctx,text,x,y,width,initial,min=27){let n=initial;while(n>min){ctx.font=`900 ${n}px Arial, sans-serif`;if(ctx.measureText(text).width<=width)break;n--}ctx.fillText(text,x,y)}
async function exportResultsPNG(){
 if(!event||event.winners.length!==event.prizes.length){notify('Confirme todos os prêmios antes de gerar a imagem.',true);return}
 const e=event;
 const W=1200,H=Math.max(1250,455+e.winners.length*235+235);
 const cnv=document.createElement('canvas');cnv.width=W;cnv.height=H;
 const c=cnv.getContext('2d');
 const bg=c.createLinearGradient(0,0,W,H);bg.addColorStop(0,'#fafffa');bg.addColorStop(1,'#e3f3e3');c.fillStyle=bg;c.fillRect(0,0,W,H);
 // Faixas laterais em verde, inspiradas no folder da reinauguração.
 c.fillStyle='#87c92e';c.beginPath();c.arc(-120,115,310,0,Math.PI*2);c.fill();
 c.fillStyle='#1a873c';c.beginPath();c.arc(W+100,H-70,285,0,Math.PI*2);c.fill();
 c.fillStyle='#122221';canvasRounded(c,76,45,W-152,168,47);c.fill();
 try{const logo=new Image();logo.src='/static/mercamell-logo.png';await new Promise((resolve)=>{logo.onload=resolve;logo.onerror=resolve});if(logo.complete&&logo.naturalWidth)c.drawImage(logo,99,57,160,139)}catch(_){}
 c.textAlign='left';c.fillStyle='#fff';c.font='900 64px Arial, sans-serif';c.fillText('MERCAMELL',275,117);
 c.fillStyle='#ff8b39';c.font='bold 35px Arial, sans-serif';c.fillText('PROMOCONTROL',278,164);
 c.textAlign='center';c.fillStyle='#173123';c.font='900 58px Arial, sans-serif';c.fillText('RESULTADO DOS SORTEIOS',W/2,284);
 c.fillStyle='#278149';c.font='bold 34px Arial, sans-serif';textFitted(c,e.name,W/2,340,1010,22);
 c.font='26px Arial, sans-serif';c.fillStyle='#536359';if(e.event_date)c.fillText('Evento: '+mdate(e.event_date),W/2,388);
 // Estrelas/confetes estáticos, sem sobrepor textos.
 for(let i=0;i<18;i++){const x=35+(i*67)%1120,y=410+(i*97)%(H-500);if(x>140&&x<1030)continue;c.save();c.translate(x,y);c.rotate((i*31)*Math.PI/180);c.fillStyle=i%2?'#f79437':'#46b34b';c.fillRect(-5,-9,10,18);c.restore()}
 e.winners.forEach((w,i)=>{
  const y=425+i*235;
  c.fillStyle='#ffffff';c.shadowColor='#193d2318';c.shadowBlur=18;c.shadowOffsetY=6;canvasRounded(c,105,y,990,209,28);c.fill();c.shadowBlur=0;c.shadowOffsetY=0;
  c.fillStyle=i===0?'#ff7d25':'#178348';canvasRounded(c,132,y+30,122,140,23);c.fill();
  c.textAlign='center';c.fillStyle='#fff';c.font='900 53px Arial, sans-serif';c.fillText((i+1)+'º',193,y+116);
  c.textAlign='left';c.fillStyle='#21834a';c.font='bold 25px Arial, sans-serif';textFitted(c,w.prize.toUpperCase(),282,y+48,730,22);
  c.fillStyle='#162c24';textFitted(c,w.name,282,y+113,730,28);
  c.font='bold 28px Arial, sans-serif';c.fillStyle='#f07922';c.fillText('NÚMERO '+digits(w.number),282,y+167);
 });
 const footerY=H-167;
 c.fillStyle='#142825';canvasRounded(c,105,footerY,990,109,32);c.fill();
 c.fillStyle='#fff';c.font='bold 33px Arial, sans-serif';c.textAlign='center';c.fillText('Obrigado por participar!',W/2,footerY+47);
 c.font='22px Arial, sans-serif';c.fillStyle='#bfe6c4';c.fillText('Mercamell • PromoControl',W/2,footerY+84);
 const file='Mercamell_Resultado_'+(e.name||'evento').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/gi,'_').slice(0,55)+'.png';
 cnv.toBlob(blob=>{if(!blob){notify('Não foi possível gerar a imagem.',true);return}const href=URL.createObjectURL(blob),a=document.createElement('a');a.href=href;a.download=file;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(href),12000)},'image/png');
}