import {App} from '@modelcontextprotocol/ext-apps';
const app=new App({name:'Agent Visual Bridge',version:'0.2.0'},{},{autoResize:true});
let installed=false;
(window as any).avbAppCall=async(path:string,body:any,proposal:any)=>{
 const result=await app.callServerTool({name:'visual_bridge_app_action',arguments:{review_id:proposal.review_id,path,body:body||null}});
 if(result.isError)throw new Error(result.content.filter((x:any)=>x.type==='text').map((x:any)=>x.text).join('\n'));
 const data=(result.structuredContent as any)?.data;
 if(path==='/api/submit'){
  try{await app.sendMessage({role:'user',content:[{type:'text',text:'Décisions humaines enregistrées. Reçu '+data.receipt_id+'. Consulte ce reçu avant de poursuivre.'}]});}catch{}
 }
 return data;
};
app.ontoolresult=(result:any)=>{
 const html=result._meta?.review_html;
 if(installed||typeof html!=='string')return;
 installed=true;
 const doc=new DOMParser().parseFromString(html,'text/html');
 document.title=doc.title;
 for(const style of doc.querySelectorAll('style'))document.head.appendChild(style.cloneNode(true));
 const scripts=Array.from(doc.body.querySelectorAll('script'));
 for(const s of scripts)s.remove();
 document.body.replaceChildren(...Array.from(doc.body.childNodes));
 for(const source of scripts){const script=document.createElement('script');for(const attr of source.attributes)script.setAttribute(attr.name,attr.value);script.textContent=source.textContent;document.body.appendChild(script);}
};
function applyHostTheme(context:any){
 const root=document.documentElement;
 if(!context?.theme)return;
 root.style.colorScheme=context.theme;
 const colors=context.theme==='light'?{bg:'#f5f7fb',surface:'#ffffff',text:'#162136',muted:'#42536e',line:'#697b96',accent:'#245aa5'}:{bg:'#0c1320',surface:'#182238',text:'#edf2ff',muted:'#b8c5df',line:'#647493',accent:'#92b5ff'};
 for(const [name,value] of Object.entries(colors))root.style.setProperty('--'+name,value);
}
app.onhostcontextchanged=applyHostTheme;
app.connect().then(()=>applyHostTheme(app.getHostContext())).catch(error=>{document.body.textContent='Interface native indisponible : '+error.message;});
