"""Upload synthetic fixtures using API authorization, not privileged SQL."""
import argparse
import os
from pathlib import Path
import httpx

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url',default='http://localhost:8000')
    args = parser.parse_args()
    with httpx.Client(base_url=args.url,timeout=60,trust_env=False) as client:
        response = client.post('/auth/login',json={'email':os.environ['ADMIN_EMAIL'],'password':os.environ['ADMIN_PASSWORD']})
        response.raise_for_status()
        client.headers['Authorization'] = 'Bearer '+response.json()['access_token']
        def send(method,path,**kwargs):
            result = client.request(method,path,**kwargs)
            result.raise_for_status()
            return result.json()
        send('POST','/admin/users',json={'email':'developer@demo.internal','password':os.environ['DEMO_PASSWORD'],'role':'developer'})
        public = send('POST','/collections',json={'name':'Démo — documentation technique'})['id']
        private = send('POST','/collections',json={'name':'Démo — confidentiel'})['id']
        send('PUT',f'/admin/roles/developer/collections/{public}',json={'can_write':True})
        for path in sorted((Path(__file__).parent/'corpus').iterdir()):
            target = private if path.name=='confidential.txt' else public
            with path.open('rb') as file:
                send('POST',f'/collections/{target}/documents',files={'file':(path.name,file)})
        print('Corpus chargé. Attendre que les documents soient ready avant l’évaluation.')

if __name__=='__main__':
    main()
