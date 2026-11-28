"""Optional deterministic Codex tool-handler test. Local fake provider; no model call.

Uses only a synthetic key and isolated client home. Never imports owner auth.
"""
import json,sys,tempfile,threading,subprocess,os,signal
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parent));import guarded_task as gate


def exact_denial(value):
    expected='approval policy is never; reject command — you cannot ask for escalated permissions if the approval policy is never'
    return (value.get('type')=='function_call_output' and value.get('call_id')=='call_fixture' and
            isinstance(value.get('output'),str) and value['output'].casefold()==expected)


def main():
    root=Path(tempfile.mkdtemp(prefix='guard-forced-proof-')).resolve();w=root/'worker';w.mkdir();d=root/'driver';d.mkdir();ch=root/'client';ch.mkdir();pfile=w/'protected.txt';pfile.write_text('UNCHANGED');a=w/'allowed.txt';a.write_text('ALLOWED')
    code='text(await tools.exec_command('+json.dumps({'cmd':'echo BAD > '+str(pfile),'sandbox_permissions':'require_escalated','justification':'Synthetic negative test; reject this request.'})+'));'
    seen={'requests':0,'tool_output_seen':False,'denied':False,'tool_names':[],'transport_errors':0}
    class Handler(BaseHTTPRequestHandler):
     def log_message(self,*a):pass
     def do_POST(self):
      n=int(self.headers.get('Content-Length','0'))
      if n>2*1024*1024:self.send_error(413);return
      body=json.loads(self.rfile.read(n));seen['requests']+=1
      def walk(v):
       if isinstance(v,dict):
        if v.get('type') in ['custom_tool_call_output','function_call_output']:
         seen['tool_output_seen']=True;seen['denied']|=exact_denial(v)
        if v.get('name') and v.get('type') in ['custom','function']:seen['tool_names'].append(v['name'])
        for x in v.values():walk(x)
       if isinstance(v,list):
        for x in v:walk(x)
      walk(body)
      rid='resp_fixture_'+str(seen['requests'])
      if seen['requests']==1:item={'type':'function_call','id':'ctc_fixture','call_id':'call_fixture','name':'exec_command','arguments':json.dumps({'cmd':'echo BAD > '+str(pfile),'sandbox_permissions':'require_escalated','justification':'Synthetic negative test; reject this request.'}),'status':'completed'}
      else:item={'type':'message','id':'msg_fixture','role':'assistant','content':[{'type':'output_text','text':'Synthetic tool-handler test complete.','annotations':[]}],'status':'completed'}
      response={'id':rid,'object':'response','status':'completed','output':[item],'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}
      events=[{'type':'response.created','response':dict(response,status='in_progress',output=[])},
       {'type':'response.output_item.added','output_index':0,'item':dict(item,status='in_progress')},
       {'type':'response.output_item.done','output_index':0,'item':item},
       {'type':'response.completed','response':response}]
      raw=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
      self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers()
      try:self.wfile.write(raw)
      except BrokenPipeError:seen['transport_errors']+=1
    server=HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    packet={'source':{'root':str(w),'files':{'allowed.txt':'x','protected.txt':'x'}},'writable':['allowed.txt'],'model':'fixture-model'}
    args=gate.client_args(subprocess.check_output(['which','codex'],text=True).strip(),d,packet)
    args+=['-c','model_provider="fixture"','-c','model_providers.fixture='+gate.toml({'name':'Local synthetic test','base_url':'http://127.0.0.1:'+str(server.server_address[1])+'/v1','wire_api':'responses','env_key':'GUARD_FIXTURE_API_KEY'}),'Execute the synthetic test tool call.']
    env={'PATH':'/usr/bin:/bin','HOME':str(root),'CODEX_HOME':str(ch),'GUARD_FIXTURE_API_KEY':'synthetic-not-a-real-key'}
    proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,close_fds=True,start_new_session=True)
    try:
     out,err=proc.communicate(timeout=45);seen.update(exit=proc.returncode,protected_unchanged=pfile.read_text()=='UNCHANGED',fixture=str(root))
     seen['result']='passed' if seen['requests']==2 and seen['transport_errors']==0 and seen['tool_output_seen'] and seen['denied'] and seen['protected_unchanged'] and seen['exit']==0 else 'failed'
     seen.pop('tool_names',None);seen.pop('fixture',None)
     seen['test_boundary']='native_exec_handler_with_local_fixture_provider_not_a_live_model'
     seen['executable_sha256']=gate.executable_digest(Path(args[0]))
     print(json.dumps(seen))
     if seen['result']!='passed':raise SystemExit(1)
    finally:
     if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
     server.shutdown();server.server_close()
     import shutil
     shutil.rmtree(root)

if __name__=='__main__':main()
