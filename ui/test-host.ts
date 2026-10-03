import {AppBridge,PostMessageTransport} from '@modelcontextprotocol/ext-apps/app-bridge';
(window as any).startAvbHost=async(config:any)=>{
 const iframe=document.createElement('iframe');iframe.style.width='100%';iframe.style.height='900px';iframe.setAttribute('sandbox','allow-scripts allow-same-origin');document.body.append(iframe);
 const bridge=new AppBridge(null,{name:'AVB qualification host',version:'1.0.0'},{serverTools:{},message:{},logging:{}},{hostContext:{theme:'dark'}});
 bridge.oncalltool=async(params:any)=>{
  if(params.name!=='visual_bridge_app_action')throw new Error('Unexpected tool');
  const {path,body}=params.arguments;
  const response=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-AVB-Token':config.token},body:body?JSON.stringify(body):undefined});
  const data=await response.json();return {isError:!response.ok,content:[{type:'text',text:JSON.stringify(data)}],structuredContent:{data}};
 };
 bridge.onmessage=async(params:any)=>{(window as any).humanMessage=params;return {};};
 bridge.oninitialized=async()=>{await bridge.sendToolInput({arguments:{review_id:config.review.review_id}});await bridge.sendToolResult({content:[],structuredContent:{review:config.review},_meta:{review_html:config.html}});};
 await bridge.connect(new PostMessageTransport(iframe.contentWindow!,iframe.contentWindow!));
 iframe.srcdoc=config.resource;
 (window as any).hostBridge=bridge;
};
