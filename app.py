#!/usr/bin/env python3
"""Run the local job matcher or its offline workflow demo."""
import argparse
import json
from core.settings import Settings
from composition import build_services
from adapters.demo import SAMPLE_RESUME
from workflows.job_matcher import JobWorkflow


def main():
    parser=argparse.ArgumentParser(description='Proof — résumé-based job matching')
    sub=parser.add_subparsers(dest='command',required=True)
    serve=sub.add_parser('serve',help='Start the local browser app')
    serve.add_argument('--port',type=int,default=8765)
    demo=sub.add_parser('demo',help='Run the synthetic workflow without API keys')
    demo.add_argument('--count',type=int,default=5)
    args=parser.parse_args()
    if args.command=='serve':
        import socket
        import uvicorn
        from api.app import create_app
        # Claim the port before opening storage, which recovers interrupted runs.
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            try: listener.bind(('127.0.0.1',args.port))
            except OSError: parser.error('Port %s is already in use. The running app was left untouched.'%args.port)
            server=uvicorn.Server(uvicorn.Config(create_app(),host='127.0.0.1',port=args.port))
            server.run(sockets=[listener])
    else:
        from core.models import SearchRequest
        SearchRequest('sample',count=args.count).validate()
        settings=Settings();services=build_services(settings,demo=True)
        workflow=JobWorkflow(services.search,services.extract,services.reasoner,settings,lambda e:None)
        result=services.runner.run(workflow,{'resume_text':SAMPLE_RESUME,'query':'Developer advocate, remote, US',
                 'count':args.count,'max_rounds':settings.max_rounds,'demo':True})
        print(json.dumps(result,indent=2))


if __name__=='__main__':main()
