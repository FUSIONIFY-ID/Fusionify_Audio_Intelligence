import argparse
import json
import os
from pathlib import Path
from .engine import doctor
from .service import Service


def main():
    ap=argparse.ArgumentParser(description='Fusionify Audio Intelligence local MVP')
    ap.add_argument('--media-root',default=os.environ.get('FAI_MEDIA_ROOT'))
    ap.add_argument('--state-root',default=os.environ.get('FAI_STATE_ROOT',str(Path.home()/'.fusionify-audio')))
    sub=ap.add_subparsers(dest='action',required=True)
    sub.add_parser('doctor')
    sub.add_parser('serve')
    analyze=sub.add_parser('analyze');analyze.add_argument('audio_path')
    plan=sub.add_parser('plan');plan.add_argument('analysis_id');plan.add_argument('--intensity',default='medium')
    args=ap.parse_args()
    if args.action=='doctor':print(json.dumps(doctor(),indent=2));return
    if not args.media_root:ap.error('Set FAI_MEDIA_ROOT or --media-root to your music folder.')
    service=Service(Path(args.media_root),Path(args.state_root))
    try:
        if args.action=='serve':
            from .server import build_server
            build_server(service).run(transport='stdio')
        elif args.action=='analyze':print(json.dumps(service.analyze(args.audio_path),indent=2,allow_nan=False))
        elif args.action=='plan':print(json.dumps(service.plan(args.analysis_id,intensity=args.intensity),indent=2,allow_nan=False))
    finally:service.close()


if __name__=='__main__':main()
