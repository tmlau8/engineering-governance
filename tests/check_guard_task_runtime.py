"""Optional native Codex controller integration test; local fixture model, no bill.

No real project/data/credentials. Exercises actual prepare/approval/claim/Popen,
with only model transport and test home replaced. Synthetic usage stays private
in the temporary test home; never imported into the user's dashboard.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tooling'),str(ROOT/'evidence'),str(ROOT/'tests')]
import guarded_task as gate
import review_fixtures


def main():
    with tempfile.TemporaryDirectory(prefix='guard-integrated-') as temporary:
        base=Path(temporary).resolve();worker=base/'worker';worker.mkdir();owner=base/'owner';owner.mkdir(mode=0o700)
        home=base/'isolated-home';(home/'.codex/sessions').mkdir(parents=True,mode=0o700)
        def git(*args):return subprocess.check_output(['/usr/bin/git','-C',str(worker),*args],stderr=subprocess.DEVNULL).decode().strip()
        git('init','-b','feature/synthetic');git('config','user.name','Synthetic');git('config','user.email','synthetic@example.invalid');git('remote','add','origin','https://github.com/fixture/guard.git')
        target=worker/'test_code.py';target.write_text('BEFORE\n');(worker/'spec.md').write_text('SYNTHETIC CONTROL TEST: write exactly GUARDED_OK to test_code.py. No real project claim, participant data or external dependency.\n')
        git('add','.');git('commit','-m','synthetic reviewed source');head=git('rev-parse','HEAD')
        adapter=json.loads((ROOT/'adapters/senior-concierge.json').read_text());adapter['repository']='fixture/guard';adapter_file=base/'adapter.json';adapter_file.write_text(json.dumps(adapter))
        subject=review_fixtures.subject(head=head,base=head);subject.update(repository='fixture/guard',change_id='SYNTHETIC-E2E')
        bundle=base/'synthetic-reviews.json';bundle.write_text(json.dumps(review_fixtures.bundle(subject)))
        executable=Path(shutil.which('codex')).resolve();receipt={'contract':gate.CONTRACT,'executable_sha256':gate.executable_digest(executable),'controller_sha256':gate.code_digest(),'frontend_and_child_behavior_verified':True}
        (owner/'client-capability.json').write_text(json.dumps(receipt));(owner/'client-capability.json').chmod(0o600)
        state={'requests':0,'tool_output':False}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                size=int(self.headers.get('Content-Length','0'))
                if size>2*1024*1024:self.send_error(413);return
                data=json.loads(self.rfile.read(size));state['requests']+=1
                for value in data.get('input',[]):
                    if isinstance(value,dict) and value.get('type')=='function_call_output' and value.get('call_id')=='fixture_write':state['tool_output']=True
                if state['requests']==1:
                    item={'type':'function_call','id':'fc_write','call_id':'fixture_write','name':'exec_command','arguments':json.dumps({'cmd':'printf "GUARDED_OK\\n" > '+shlex.quote(str(target))}),'status':'completed'}
                else:item={'type':'message','id':'fixture_done','role':'assistant','content':[{'type':'output_text','text':'Synthetic integration complete.','annotations':[]}],'status':'completed'}
                response={'id':'resp_'+str(state['requests']),'object':'response','status':'completed','output':[item],'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}
                events=[{'type':'response.created','response':dict(response,status='in_progress',output=[])},{'type':'response.output_item.added','output_index':0,'item':dict(item,status='in_progress')},{'type':'response.output_item.done','output_index':0,'item':item},{'type':'response.completed','response':response}]
                raw=''.join('event: '+x['type']+'\ndata: '+json.dumps(x)+'\n\n' for x in events).encode();self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        original_args=gate.client_args
        def fixture_transport(binary,driver,packet):
            return original_args(binary,driver,packet)+['-c','model_provider="fixture"','-c','model_providers.fixture='+gate.toml({'name':'Isolated fixture','base_url':'http://127.0.0.1:'+str(server.server_address[1])+'/v1','wire_api':'responses','requires_openai_auth':False})]
        try:
            with patch.object(Path,'home',return_value=home),patch.object(gate,'client_args',side_effect=fixture_transport):
                packet=gate.prepare(owner,worker,adapter_file,'spec.md',bundle,'SYNTHETIC-E2E','feature','builder-agent-1','synthetic-builder-session',head,['test_code.py'],'fixture-model','openai',timeout=30)
                rejected=False
                try:gate.execute(owner,packet['id'],executable)
                except ValueError:rejected=True
                if not rejected or state['requests'] or target.read_text()!='BEFORE\n':raise ValueError('UNAPPROVED_TASK_EXECUTED')
                gate.approve(owner,packet['id'],gate.digest(packet));outcome=gate.execute(owner,packet['id'],executable)
                if outcome!='completed' or target.read_text()!='GUARDED_OK\n' or state['requests']!=2 or not state['tool_output']:raise ValueError('APPROVED_NATIVE_TASK_FAILED')
                reused=False
                try:gate.execute(owner,packet['id'],executable)
                except ValueError:reused=True
                if not reused:raise ValueError('PERMIT_REUSED')
                print(json.dumps({'result':'passed','boundary':'native_client_with_local_fixture_model_transport','unapproved_blocked':rejected,'approved_native_file_effect':True,'reuse_blocked':reused,'model_requests':0,'real_task_permissions':0,'synthetic_records_imported':False}))
        finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
