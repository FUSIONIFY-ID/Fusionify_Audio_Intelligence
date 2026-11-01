import argparse
import json
import os
import time
import sys
from pathlib import Path
from .engine import doctor
from .service import Service


def main():
    ap=argparse.ArgumentParser(description='Fusionify Audio Intelligence creator workspace')
    ap.add_argument('--media-root',default=os.environ.get('FAI_MEDIA_ROOT'))
    ap.add_argument('--state-root',default=os.environ.get('FAI_STATE_ROOT',str(Path.home()/'.fusionify-audio')))
    sub=ap.add_subparsers(dest='action',required=True)
    sub.add_parser('doctor')
    sub.add_parser('serve')
    http=sub.add_parser('serve-http')
    http.add_argument('--host',default='127.0.0.1')
    http.add_argument('--port',type=int,default=8000)
    http.add_argument('--public-base-url',default=os.environ.get('FAI_PUBLIC_BASE_URL'))
    sub.add_parser('generate-token')
    analyze=sub.add_parser('analyze');analyze.add_argument('audio_path')
    plan=sub.add_parser('plan');plan.add_argument('analysis_id');plan.add_argument('--intensity',default='medium')
    for name in ('assets','projects','jobs'):sub.add_parser(name)
    profile=sub.add_parser('profile');profile.add_argument('analysis_id')
    create=sub.add_parser('create-project');create.add_argument('analysis_id');create.add_argument('--options',type=Path)
    revise=sub.add_parser('revise-project');revise.add_argument('project_id');revise.add_argument('--expected-revision',type=int,required=True);revise.add_argument('--changes',type=Path,required=True)
    render=sub.add_parser('render-project');render.add_argument('project_id');render.add_argument('--preview',action='store_true')
    for name in ('job-status','cancel-job'):
        parser=sub.add_parser(name);parser.add_argument('job_id')
    export=sub.add_parser('export-project');export.add_argument('project_id');export.add_argument('--format',choices=['json','csv'],default='json')
    beats=sub.add_parser('beat-preview');beats.add_argument('analysis_id');beats.add_argument('--start',type=float,default=0);beats.add_argument('--duration',type=float)
    args=ap.parse_args()
    if args.action=='generate-token':
        import secrets
        print(secrets.token_urlsafe(48));return
    if args.action=='doctor':print(json.dumps(doctor(),indent=2));return
    if not args.media_root:ap.error('Set FAI_MEDIA_ROOT or --media-root to your music folder.')
    import_hosts={h.strip() for h in os.environ.get('FAI_IMPORT_HOSTS','').split(',') if h.strip()}
    service=Service(Path(args.media_root),Path(args.state_root),import_hosts)
    try:
        if args.action=='serve':
            from .server import build_server
            build_server(service).run(transport='stdio')
        elif args.action=='serve-http':
            from .http_app import build_http_app
            import uvicorn
            token=os.environ.get('FAI_API_TOKEN','')
            base=args.public_base_url or f'http://127.0.0.1:{args.port}'
            app=build_http_app(service,token,base)
            uvicorn.run(app,host=args.host,port=args.port,access_log=False)
        else:
            result=None
            if args.action=='analyze':result=service.analyze(args.audio_path)
            elif args.action=='plan':result=service.plan(args.analysis_id,intensity=args.intensity)
            elif args.action=='profile':result=service.profile(args.analysis_id)
            elif args.action=='assets':result=service.assets()
            elif args.action=='projects':result=service.list_projects()
            elif args.action=='jobs':result=service.list_jobs()
            elif args.action=='create-project':result=service.create_project(args.analysis_id,json.loads(args.options.read_text()) if args.options else {})
            elif args.action=='revise-project':result=service.revise_project(args.project_id,args.expected_revision,json.loads(args.changes.read_text()))
            elif args.action=='job-status':result=service.status(args.job_id)
            elif args.action=='cancel-job':result=service.cancel_job(args.job_id)
            elif args.action=='export-project':result=service.export(args.project_id,args.format)
            elif args.action in ('render-project','beat-preview'):
                job=service.render_project(args.project_id,args.preview) if args.action=='render-project' else service.beat_preview(args.analysis_id,args.start,args.duration)
                print('Queued '+job['job_id'],file=sys.stderr)
                while True:
                    result=service.status(job['job_id'])
                    if result['status'] in ('completed','failed','cancelled','interrupted'):break
                    time.sleep(.2)
                if result['status']!='completed':raise ValueError(result.get('error',result['status']))
            print(json.dumps(result,indent=2,allow_nan=False))
    finally:service.close()


if __name__=='__main__':main()
