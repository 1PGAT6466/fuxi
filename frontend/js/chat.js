// ===== 对话 =====
let chatHistory=[];
async function sendChat(useWeb){
  const input=document.getElementById('chatInput');
  const q=input.value.trim();if(!q)return;
  input.value='';input.style.height='auto';
  const empty=document.getElementById('chatEmpty');if(empty)empty.remove();
  const prefix=useWeb?'🌐 ':'';
  appendMsg('user',prefix+q);chatHistory.push({role:'user',content:q});
  const lid=appendMsg('loading','<span class=loading-dots>AI 思考中<span>.</span><span>.</span><span>.</span></span>'+(useWeb?' (联网搜索)':''));
  try{
    const apiPath=useWeb?'/api/antenna/search':'/api/chat';
    const body=useWeb?{query:q}:{query:q,history:chatHistory.slice(-6),stream:false};
    const d=await api(apiPath,{method:'POST',body:body});
    removeMsg(lid);
    const answer=d.answer||'未能生成回答';
    appendMsg('ai',answer,d.sources,d.trace);
    chatHistory.push({role:'assistant',content:answer});
  }catch(e){removeMsg(lid);appendMsg('error','请求失败: '+e.message)}
}

function appendMsg(role,content,sources,trace){
  const c=document.getElementById('chatMsgs');
  const id='m-'+Date.now();
  const div=document.createElement('div');div.id=id;div.className='msg '+role;
  if(role==='user'){div.innerHTML=`<div class="msg-bubble">${esc(content)}</div>`}
  else if(role==='loading'){div.innerHTML=`<div class="typing">${content}</div>`}
  else if(role==='error'){div.innerHTML=`<div class="msg-bubble" style="color:var(--error)">${esc(content)}</div>`}
  else{
    let html=`<div class="msg-bubble">${typeof marked!=='undefined'?marked.parse(content):content}</div>`;
    if(sources&&sources.length){html+=`<div class="msg-sources">${sources.slice(0,5).map((s,i)=>`<span class="source-chip">📄 ${esc(s.file_name||s.title||'Ref '+(i+1))}</span>`).join('')}</div>`}
    if(trace&&trace.steps){html+=`<div class="msg-trace">${trace.steps.map(s=>`<div class="trace-step"><span class="tool">${s.tool||s.type}</span><span>${s.status||''}</span><span class="ms">${s.latency_ms?s.latency_ms.toFixed(0)+'ms':''}</span></div>`).join('')}</div>`}
    div.innerHTML=html;
  }
  c.appendChild(div);c.scrollTop=c.scrollHeight;return id;
}
function removeMsg(id){const el=document.getElementById(id);if(el)el.remove()}
