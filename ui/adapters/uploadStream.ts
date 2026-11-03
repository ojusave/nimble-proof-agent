import type {ActivityEvent,Resume} from '../core/types';

export async function uploadResume(url: string,file: File,onProgress?: (event: ActivityEvent) => void): Promise<Resume> {
  const body=new FormData();body.append('file',file);
  const response=await fetch(url,{method:'POST',body,headers:{Accept:'text/event-stream'}});
  if(!response.ok || !response.body) throw new Error('The résumé service could not accept this upload.');
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';let sequence=0;
  try {
    while(true) {
      const {value,done}=await reader.read();buffer+=decoder.decode(value,{stream:!done});
      let boundary;
      while((boundary=buffer.indexOf('\n\n'))>=0) {
        const packet=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2);
        const type=packet.split('\n').find(line => line.startsWith('event: '))?.slice(7);
        const data=packet.split('\n').filter(line => line.startsWith('data: ')).map(line => line.slice(6)).join('\n');
        if(!data) continue;
        const item=JSON.parse(data);
        if(type==='activity') onProgress?.({...item,seq:++sequence});
        if(type==='resume') return item as Resume;
        if(type==='error') throw new Error(item.detail || 'Résumé parsing failed.');
      }
      if(done) throw new Error('The upload connection ended before a result arrived. Check saved résumés before retrying.');
    }
  } finally {reader.releaseLock();}
}
