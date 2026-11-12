'use strict';
/* Mercamell PromoControl v3.1 — sorteio ao vivo, sem dependências externas. */
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
function prizeImageHTML(order){return event?.prize_images?.[order]?`<img class="draw-prize-photo" src="${esc(event.prize_images[order])}" alt="Imagem do prêmio">`:''}
function loadingView(prize,secs){drawOverlay(modalFrame('O GRANDE MOMENTO',esc(prize),`${prizeImageHTML(event.winners.length+1)}<p class="modal-subtitle">Preparando o resultado...</p><div class="countdown-circle" id="countdownValue" aria-live="polite">${secs||'★'}</div><p class="modal-subtitle" id="countdownCaption">${secs?'O sorteio começa em instantes':'Selecionando um número...'}</p>`,`<span class="smalltxt">Aguarde a conclusão da seleção.</span>`))}
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
 drawOverlay(modalFrame(`PRÊMIO ${p.prize_order} DE ${event.prizes.length}`,esc(p.prize),`${prizeImageHTML(p.prize_order)}<p class="modal-subtitle">Número selecionado</p><div class="result-number">${digits(p.number)}</div><div class="draw-result-owner">${name}</div>${apto}<p class="draw-result-help">Confirme o ganhador ou realize um novo sorteio se estiver ausente.</p>`,`<button class="btn secondary large" data-draw-redraw>↻ Resortear este prêmio</button><button class="btn orange large" data-draw-confirm>✓ Confirmar ganhador</button><button class="btn secondary" data-draw-close>Fechar tela</button>`))
}
async function confirmDraw(){
 if(drawBusy||!event?.pending_draw)return;drawBusy=true;
 const p=event.pending_draw;
 try{
  await act('confirm_draw',{event_id:event.id});
  await load();
  const final=event.winners.length>=event.prizes.length;
  drawOverlay(modalFrame('GANHADOR CONFIRMADO',esc(p.prize),`${prizeImageHTML(p.prize_order)}<div class="result-number">${digits(p.number)}</div><div class="draw-result-owner">${esc(p.name)}</div><div class="winner-apartment">Apartamento ${esc(p.apartment||'não informado')}</div><p class="modal-subtitle">Resultado salvo com sucesso.</p>`,final?`<button class="btn orange large" data-draw-final>★ Avançar para os 3 ganhadores</button>`:`<button class="btn orange large" data-draw-next>→ Prosseguir para o próximo prêmio</button>`))
 }catch(ex){notify(ex.message,true)}finally{drawBusy=false}
}
function showSummary(){
 if(!event||event.winners.length!==event.prizes.length)return;
 drawOverlay(modalFrame('RESULTADO FINAL','Parabéns aos ganhadores!',`<p class="modal-subtitle">${esc(event.name)}${event.event_date?' • '+esc(mdate(event.event_date)):''}</p><div class="winner-summary-grid">${event.winners.map((w,i)=>`<div class="winner-summary-row"><div class="winner-rank">${i+1}º</div>${event.prize_images?.[i+1]?`<img class="summary-prize-photo" src="${esc(event.prize_images[i+1])}" alt="Prêmio ${esc(w.prize)}">`:''}<div class="winner-info"><small>${esc(w.prize)}</small><strong>${esc(w.name)}</strong><span>Apartamento ${esc(w.apartment||'não informado')} • Número ${digits(w.number)}</span></div></div>`).join('')}</div><p class="summary-hint">A imagem compartilhável inclui prêmio, número, nome, apartamento e foto (se houver). Não inclui telefone ou dados de compras.</p>`,`<button class="btn orange large" data-draw-export>↓ Exportar imagem PNG</button><button class="btn secondary large" data-draw-close>Fechar</button>${recordingActive()?'<button class="btn secondary large" data-record-stop>■ Finalizar vídeo</button>':''}`))
}
function loadDrawImage(src){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=src})}
function canvasRounded(ctx,x,y,w,h,r){ctx.beginPath();ctx.roundRect(x,y,w,h,r)}
function textFitted(ctx,text,x,y,width,initial,min=27){let n=initial;while(n>min){ctx.font=`900 ${n}px Arial, sans-serif`;if(ctx.measureText(text).width<=width)break;n--}ctx.fillText(text,x,y)}
async function exportResultsPNG(){
 if(!event||event.winners.length!==event.prizes.length){notify('Confirme todos os prêmios antes de gerar a imagem.',true);return}
 const e=event;
 const W=1200,H=Math.max(1370,425+e.winners.length*262+240);
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
 for(const [i,w] of e.winners.entries()){
  const y=425+i*262, order=i+1, photo=e.prize_images?.[order];
  c.fillStyle='#ffffff';c.shadowColor='#193d2318';c.shadowBlur=18;c.shadowOffsetY=6;canvasRounded(c,105,y,990,232,28);c.fill();c.shadowBlur=0;c.shadowOffsetY=0;
  c.fillStyle=i===0?'#ff7d25':'#178348';canvasRounded(c,132,y+40,122,146,23);c.fill();
  c.textAlign='center';c.fillStyle='#fff';c.font='900 53px Arial, sans-serif';c.fillText(order+'º',193,y+128);
  c.textAlign='left';c.fillStyle='#21834a';c.font='bold 28px Arial, sans-serif';textFitted(c,w.prize.toUpperCase(),282,y+48,photo?518:745,22);
  c.fillStyle='#162c24';textFitted(c,w.name,282,y+108,photo?518:740,25);
  c.font='bold 25px Arial, sans-serif';c.fillStyle='#3b6650';textFitted(c,'APARTAMENTO '+(w.apartment||'NÃO INFORMADO'),282,y+162,photo?518:740,19);
  c.font='bold 31px Arial, sans-serif';c.fillStyle='#f07922';c.fillText('NÚMERO '+digits(w.number),282,y+205);
  if(photo){
   try{
    const img=await loadDrawImage(photo);
    const ix=854,iy=y+25,iw=213,ih=182;
    c.fillStyle='#f1f7f3';canvasRounded(c,ix,iy,iw,ih,14);c.fill();
    c.save();canvasRounded(c,ix,iy,iw,ih,14);c.clip();
    const ratio=Math.min(iw/img.naturalWidth,ih/img.naturalHeight);
    c.drawImage(img,ix+(iw-img.naturalWidth*ratio)/2,iy+(ih-img.naturalHeight*ratio)/2,img.naturalWidth*ratio,img.naturalHeight*ratio);
    c.restore();
   }catch(_){/* Foto opcional: os dados do ganhador continuam sendo exportados. */}
  }
 }
 const footerY=H-167;
 c.fillStyle='#142825';canvasRounded(c,105,footerY,990,109,32);c.fill();
 c.fillStyle='#fff';c.font='bold 33px Arial, sans-serif';c.textAlign='center';c.fillText('Obrigado por participar!',W/2,footerY+47);
 c.font='22px Arial, sans-serif';c.fillStyle='#bfe6c4';c.fillText('Mercamell • PromoControl',W/2,footerY+84);
 const file='Mercamell_Resultado_'+(e.name||'evento').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/gi,'_').slice(0,55)+'.png';
 cnv.toBlob(blob=>{if(!blob){notify('Não foi possível gerar a imagem.',true);return}const href=URL.createObjectURL(blob),a=document.createElement('a');a.href=href;a.download=file;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(href),12000)},'image/png');
}

// Grava a aba/tela escolhida pelo operador. O vídeo permanece no navegador até ser salvo no PC.
let screenRecorder=null,screenStream=null,recordedChunks=[],recordingEventId=null;
function recordingActive(){return !!screenRecorder&&screenRecorder.state==='recording'}
function refreshRecordingButtons(){
 const start=document.querySelector('[data-record-start]'),stop=document.querySelector('[data-record-stop]');
 const active=recordingActive();
 if(start)start.disabled=active;
 document.querySelectorAll('[data-record-stop]').forEach(x=>x.disabled=!active);
 const indicator=document.querySelector('#recordingState');
 if(indicator)indicator.textContent=active?'● Gravação em andamento':'Vídeo do sorteio (opcional)';
}
async function startDrawRecording(){
 if(recordingActive())return;
 if(!navigator.mediaDevices?.getDisplayMedia||!window.MediaRecorder){notify('Seu navegador não suporta a gravação de tela. Use Chrome ou Edge atualizado.',true);return}
 try{
  // Esta chamada precisa ocorrer diretamente após o clique do operador.
  const stream=await navigator.mediaDevices.getDisplayMedia({video:{displaySurface:'browser'},audio:true});
  const candidates=['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm'];
  const supported=candidates.find(x=>MediaRecorder.isTypeSupported(x));
  const recorder=new MediaRecorder(stream,supported?{mimeType:supported}:{});
  screenStream=stream;screenRecorder=recorder;recordedChunks=[];
  recordingEventId=event?.id;
  recorder.ondataavailable=e=>{if(e.data?.size>0)recordedChunks.push(e.data)};
  recorder.onstop=()=>{
   const mime=recorder.mimeType||'video/webm',type=mime.includes('mp4')?'mp4':'webm';
   const video=new Blob(recordedChunks,{type:mime});
   if(video.size){
    const url=URL.createObjectURL(video),link=document.createElement('a');
    link.href=url;link.download=`Mercamell_Sorteio_Evento_${recordingEventId}_${new Date().toISOString().replace(/[:.]/g,'-')}.${type}`;
    document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
    notify('Gravação concluída. Confira o vídeo salvo na pasta de downloads.',false,false);
   }else notify('A gravação terminou sem gerar vídeo. Verifique as permissões do navegador.',true);
   screenStream?.getTracks().forEach(t=>t.stop());screenStream=null;screenRecorder=null;recordedChunks=[];
   refreshRecordingButtons();
  };
  recorder.onerror=()=>notify('Houve um problema na gravação. Tente novamente.',true);
  stream.getVideoTracks()[0].addEventListener('ended',()=>stopDrawRecording());
  recorder.start(1000);refreshRecordingButtons();
  notify(stream.getAudioTracks().length?'Gravação iniciada com áudio compartilhado.':'Gravação iniciada SEM áudio. Para gravar som, compartilhe a aba com áudio.',false,false);
 }catch(ex){if(ex?.name!=='NotAllowedError')notify('Não foi possível iniciar a gravação: '+ex.message,true);else notify('Captura não autorizada. Nenhum vídeo foi iniciado.',true);refreshRecordingButtons()}
}
function stopDrawRecording(){
 if(!screenRecorder||screenRecorder.state==='inactive')return;
 try{screenRecorder.stop()}catch(ex){notify('Erro ao concluir gravação: '+ex.message,true)}
 refreshRecordingButtons();
}
window.addEventListener('beforeunload',ev=>{if(recordingActive()){ev.preventDefault();ev.returnValue=''}});