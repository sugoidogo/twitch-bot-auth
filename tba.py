from os import environ
configPath=environ.get('TBA_CONFIG_PATH','tba.ini')
print('configPath =',configPath)
from configparser import ConfigParser
config=ConfigParser()
config['NETWORK']={
    'IP':'localhost',
    'Port':5000,
}
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
config['LOG']={
    'authorization':False,
    'response':True,
    'status':True
}
config.read(configPath)
config.write(open(configPath,'w'))
print('config loaded, initializing server')

from advancedhttpserver import AdvancedHTTPServer, RequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError
from threading import Thread
from traceback import print_exc
import json,re
from urllib.parse import urlencode,parse_qsl,urlparse
from urllib.request import Request,urlopen,HTTPError

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

class TBA(RequestHandler):
    def do_GET(self):
        print(self.requestline)
        response=None
        try:
            if self.path.startswith('/tba.mjs'):
                tba=open('tba.mjs','rb').read()
                self.send_response(200)
                self.send_header('content-type','text/javascript')
                self.send_header('content-length',len(tba))
                self.end_headers()
                return self.wfile.write(tba)
            if self.path.startswith('/code'):
                query=dict(parse_qsl(urlparse(self.path).query))
                self.send_response(200)
                self.end_headers()
                get_tokens(query['code'])
                get_broadcaster_id()
                return config.write(open(configPath,'w'))
            if(self.path.startswith('/oauth2/token')):
                query=urlparse(self.path).query
                query_dict=dict(parse_qsl(query))
                if 'client_id' not in query_dict:
                    self.send_error(401)
                    return
                client_id=query_dict['client_id']
                if client_id not in config['secrets']:
                    self.send_error(403)
                    return
                client_secret=config['secrets'][client_id]
                query+='&client_secret='+client_secret
                request=Request('https://id.twitch.tv/oauth2/token',query.encode(),method='POST')
                response=urlopen(request)
                body=response.read()
                self.send_response(response.code)
                self.send_header('content-length', len(body))
                self.end_headers()
                response=None
                return self.wfile.write(body)
            if 'authorization' not in self.headers:
                return self.send_error(401,explain='missing authorization header')
            authorization=self.headers.get('authorization')
            response=urlopen(Request(config['NETWORK']['AuthURL'],headers={
                'Authorization':authorization
            }))
        except URLError as error:
            response=error
        except Exception as exception:
            self.send_error(500,str(exception))
            print_exc()
            return
        finally:
                try:
                    if(response==None):
                        return
                    if(response.code>=400):
                        self.send_error(response.code)
                        print(authorization,response.read().decode())
                    else:
                        response=json.loads(response.read().decode())
                        if('access_token' in config['api']):
                            response['tier']=get_sub(response['user_id'])
                        status=None
                        for keyword, pattern in config['DENY'].items():
                            if(status!=None):
                                break
                            if keyword in response:
                                if re.compile(pattern).match(response[keyword]):
                                    self.send_error(403)
                                    status='DENY '+keyword+' '+pattern
                                    break
                        for keyword, pattern in config['ALLOW'].items():
                            if(status!=None):
                                break
                            if keyword in response:
                                if re.compile(pattern).match(response[keyword]):
                                    self.send_response(200)
                                    status='ALLOW '+keyword+' '+pattern
                                    break
                        if(status==None):
                            self.send_error(403)
                            status='no matching ALLOW pattern'
                        for keyword, value in response.items():
                            self.send_header(keyword, value)
                        response=json.dumps(response).encode()
                        self.send_header('content-length',len(response))
                        self.end_headers()
                        self.wfile.write(response)
                        log=[]
                        if(config['LOG'].getboolean('authorization')):
                            log.append(authorization)
                        if(config['LOG'].getboolean('response')):
                            log.append(response)
                        if(config['LOG'].getboolean('status')):
                            log.append(status)
                        print(log)
                except Exception as exception:
                    self.send_error(500,str(exception))
                    print_exc()
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Headers', 'authorization,client-id')
        self.end_headers()
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin','*')
        super().end_headers()

server=AdvancedHTTPServer(TBA,(config['NETWORK']['IP'],int(config['NETWORK']['Port'])))
server=Thread(target=server.serve_forever)
server.start()

try:
    from subprocess import run
    print('startup complete, attempting systemd-notify')
    run(['systemd-notify','--ready'])
    if('access_token' not in config['api']):
        request_auth()
except Exception as e:
    print_exc()
finally:
    print('awaiting requests')
    server.join()