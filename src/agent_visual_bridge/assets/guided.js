'use strict';
const proposal=JSON.parse(document.getElementById('avb-proposal').textContent);
const runtime=AVB_RUNTIME;
const byId=id=>document.getElementById(id);
const skipped=new Set();
const drafts=new Map();
let current=null,selected=null,busy=false,requestKey=null;
const notice=message=>{byId('notice').textContent=message;};
const answered=item=>proposal.decisions?.[item.id]&&proposal.decisions[item.id].decision_kind!=='defer';
async function api(path,body){
  if(runtime.app)return window.avbAppCall(path,body,proposal);
  if(!runtime.token)throw new Error('Ouvrez cette revue avec la commande open pour enregistrer vos réponses.');
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-AVB-Token':runtime.token},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Envoi impossible. Votre réponse reste dans cette page.');
  return data;
}
function saveDraft(){
  if(current)drafts.set(current.id,{selected,answer:byId('guided-answer').value});
}
function history(){
  const container=byId('guided-responses');container.replaceChildren();
  for(const item of proposal.items){
    const decision=proposal.decisions?.[item.id];
    if(!decision)continue;
    const section=document.createElement('section');
    const heading=document.createElement('h3');heading.textContent=item.title;section.appendChild(heading);
    const labels=(decision.options||[]).map(id=>item.options.find(option=>option.id===id)?.label||id);
    for(const text of [...labels,decision.answer,decision.comment].filter(Boolean)){
      const paragraph=document.createElement('p');paragraph.textContent=text;section.appendChild(paragraph);
    }
    if(decision.decision_kind==='defer'){
      const paragraph=document.createElement('p');paragraph.textContent='Différé';section.appendChild(paragraph);
    }
    container.appendChild(section);
  }
  if(!container.childNodes.length)container.textContent='Aucune réponse envoyée.';
}
function render(focus=false){
  history();
  const count=proposal.items.filter(answered).length;
  byId('guided-progress').textContent=count+' réponse(s) enregistrée(s) · '+(proposal.items.length-count)+' question(s) restante(s)';
  current=proposal.items.find(item=>!answered(item)&&!skipped.has(item.id))||null;
  byId('guided-card').hidden=!current;byId('guided-complete').hidden=!!current;
  if(!current){
    byId('guided-complete-text').textContent=count===proposal.items.length?'Vous avez répondu à toutes les questions.':'Vous pouvez reprendre les questions restantes plus tard.';
    byId('guided-return').hidden=count===proposal.items.length;
    return;
  }
  const draft=drafts.get(current.id)||{};selected=draft.selected||null;requestKey=null;
  byId('guided-question').textContent=current.question;
  byId('guided-context').textContent=current.description;
  byId('guided-answer').value=draft.answer||'';
  byId('guided-details').open=false;
  byId('guided-help').textContent=(current.checks||[]).join('\n\n');
  byId('guided-details').hidden=!(current.checks||[]).length;
  const options=byId('guided-options');options.replaceChildren();
  for(const option of current.options){
    const button=document.createElement('button');button.type='button';button.textContent=option.label;
    button.setAttribute('aria-pressed',String(option.id===selected));
    button.addEventListener('click',()=>{
      selected=option.id;requestKey=null;
      for(const child of options.children)child.setAttribute('aria-pressed',String(child===button));
    });options.appendChild(button);
  }
  if(focus)byId('guided-question').focus();
}
function lock(value){
  for(const element of document.querySelectorAll('#guided-card button,#guided-answer'))element.disabled=value;
}
byId('guided-answer').addEventListener('input',()=>{requestKey=null;});
byId('guided-send').addEventListener('click',async()=>{
  if(busy||!current)return;
  const answer=byId('guided-answer').value.trim();
  if(!selected&&!answer){notice('Choisissez une option ou écrivez une réponse.');return;}
  saveDraft();busy=true;lock(true);requestKey=requestKey||crypto.randomUUID();
  const item=current;
  try{
    const receipt=await api('/api/submit',{review_id:proposal.review_id,revision:proposal.revision,request_key:requestKey,decisions:[{id:item.id,fingerprint:item.authorization_fingerprint,decision_kind:selected?'choose':'answer',options:selected?[selected]:[],answer,comment:'',constraints:[]}]});
    for(const decision of receipt.decisions){proposal.decisions=proposal.decisions||{};proposal.decisions[decision.id]=decision;}
    byId('avb-feedback').textContent=JSON.stringify(receipt);
    drafts.delete(item.id);notice('Réponse enregistrée.');render(true);
  }catch(error){notice(error.message+' Si la revue a changé, rechargez pour lire la nouvelle version.');}
  finally{busy=false;lock(false);}
});
byId('guided-skip').addEventListener('click',()=>{
  if(busy||!current)return;
  saveDraft();skipped.add(current.id);notice('Question laissée en attente.');render(true);
});
byId('guided-return').addEventListener('click',()=>{skipped.clear();render(true);});
render();
if(!runtime.token&&!runtime.app){lock(true);notice('Aperçu : ouvrez la revue avec la commande open pour répondre.');}
