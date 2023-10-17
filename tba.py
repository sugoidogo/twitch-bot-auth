from os import environ
configPath=environ.get('TBA_CONFIG_PATH','tba.ini')
print('configPath =',configPath)
from configparser import ConfigParser
config=ConfigParser()
config['api']={
    'AuthURL':'https://id.twitch.tv/oauth2/validate',
    'client_id':'',
    'client_secret':'',
    'redirect_uri':''
}
config['DENY']={}
config['ALLOW']={
    'client_id':'.*',
    'user_id':'.*'
}
config['secrets']={}
config.read(configPath)
config.write(open(configPath,'w'))

import json,re
from urllib.parse import urlencode,parse_qsl,urlparse
from urllib.request import Request,urlopen,HTTPError
from urllib.error import URLError

def get_broadcaster_id():
    headers={
        'Client-ID':config['api']['client_id'],
        'Authorization':'Bearer '+config['api']['access_token']
    }
    url='https://api.twitch.tv/helix/users'
    request=Request(url,headers=headers)
    response=json.loads(urlopen(request).read().decode())
    config['api']['broadcaster_id']=response['data'][0]['id']

def request_auth():
    if(config['api']['client_id']=='' or config['api']['client_secret']==''):
        return print('Please add client_id and client_secret to your config to allow checking subscriptions')
    query={
        'response_type':'code',
        'scope':'channel:read:subscriptions',
        'client_id':config['api']['client_id']
    }
    location='https://id.twitch.tv/oauth2/authorize?'
    location+=urlencode(query)
    location+='&redirect_uri='+config['api']['redirect_uri']
    print('Visit the url below to authorize checking subscriptions')
    print(location)

def refresh_tokens():
    try:
        print('refreshing access token')
        query={
            'refresh_token':config['api']['refresh_token'],
            'client_id':config['api']['client_id'],
            'client_secret':config['api']['client_secret'],
            'grant_type':'refresh_token'
        }
        url='https://id.twitch.tv/oauth2/token'
        query=urlencode(query)
        query+='&redirect_uri='+config['api']['redirect_uri']
        request=Request('https://id.twitch.tv/oauth2/token',query.encode(),method='POST')
        response=json.loads(urlopen(request).read().decode())
        config['api']['access_token']=response['access_token']
        config['api']['refresh_token']=response['refresh_token']
        config.write(open(configPath,'w'))
    except HTTPError as error:
        request_auth()
        raise error

def get_tokens(code):
    query={
        'code':code,
        'client_id':config['api']['client_id'],
        'client_secret':config['api']['client_secret'],
        'grant_type':'authorization_code'
    }
    url='https://id.twitch.tv/oauth2/token'
    query=urlencode(query)
    query+='&redirect_uri='+config['api']['redirect_uri']
    request=Request('https://id.twitch.tv/oauth2/token',query.encode(),method='POST')
    response=json.loads(urlopen(request).read().decode())
    config['api']['access_token']=response['access_token']
    config['api']['refresh_token']=response['refresh_token']

def get_sub(user_id):
    headers={
        'client-id':config['api']['client_id'],
        'Authorization':'Bearer '+config['api']['access_token']
    }
    query={
        'broadcaster_id':config['api']['broadcaster_id'],
        'user_id':user_id
    }
    url='https://api.twitch.tv/helix/subscriptions?'
    url+=urlencode(query)
    request=Request(url,headers=headers)
    try:
        response=json.loads(urlopen(request).read().decode())
        if len(response['data']) == 0:
            return '0000'
        return response['data'][0]['tier']
    except HTTPError:
        print_exc()
        refresh_tokens()
        return get_sub(user_id)

def request_handler(method='GET',path='/',params={},headers={},body='') -> tuple[str,int,dict]:
    print(method+' '+path)
    if(method=='OPTIONS'):
        return '',204,{
            'Access-Control-Allow-Headers':'authorization,client-id',
        }
    if(method=='GET'):
        try:
            if path.startswith('/tba.mjs'):
                tba=open('tba.mjs','r').read()
                return open('tba.mjs','r').read(),200,{
                    'content-type':'text/javascript',
                }
            if path.startswith('/code'):
                get_tokens(params['code'])
                get_broadcaster_id()
                config.write(open(configPath,'w'))
                script='<script>window.close()</script>'
                return script,200,{
                    'content-type':'text/html'
                }
            if path.startswith('/oauth2/token'):
                if 'client_id' not in params:
                    error='client_id not in params'
                    return error,401,{
                        'content-type':'text/plain'
                    }
                client_id=params['client_id']
                if client_id not in config['secrets']:
                    error='client_id not in config secrets'
                    return error,403,{
                        'content-type':'text/plain'
                    }
                client_secret=config['secrets'][client_id]
                params['client_secret']=client_secret
                query='?'
                for key,val in params.items():
                    query+=key+'='+val+'&'
                request=Request('https://id.twitch.tv/oauth2/token',query.encode(),method='POST')
                response=urlopen(request)
                body=response.read().decode()
                return body,response.code,response.headers
            if path.startswith('/oauth2/validate'):
                if 'authorization' not in headers:
                    error='authorization not in headers'
                    return error,401,{
                        'content-type':'text/plain'
                    }
                authorization=headers.get('authorization')
                response=urlopen(Request(config['NETWORK']['AuthURL'],headers={
                    'Authorization':authorization
                }))
                response=json.loads(response.read().decode())
                if('access_token' in config['api']):
                    response['tier']=get_sub(response['user_id'])
                status=None
                for keyword, pattern in config['DENY'].items():
                    if(status!=None):
                        break
                    if keyword in response:
                        if re.compile(pattern).match(response[keyword]):
                            return json.dumps(response),403,response.items()
                for keyword, pattern in config['ALLOW'].items():
                    if(status!=None):
                        break
                    if keyword in response:
                        if re.compile(pattern).match(response[keyword]):
                            return json.dumps(response),204,response.items()
                return json.dumps(response),403,response.items()
            return '',404,{}
        except URLError as response:
            error=response.read().decode()
            return error,response.code,response.headers
        except Exception as exception:
            from traceback import format_exc
            error=format_exc()
            return error,500,{
                'content-type':'text/plain'
            }

if __name__ == '__main__':
    import httpserverless
    httpserverless.start_server(request_handler)