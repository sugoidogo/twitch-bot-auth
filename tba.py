from os import environ
sqldb=environ.get('SQLDB') or 'tba.db' # is there a standard for this environment variable?

if sqldb.endswith('.db'):
    import sqlite3 as sql
else:
    import pyodbc as sql

sql_connection=sql.connect(sqldb)
sql_cursor=sql_connection.cursor()

read_config=lambda:dict(sql_cursor.execute('select * from config').fetchall())

try:
    config=read_config()
except sql.OperationalError:
    sql_cursor.execute('create table config(key,value)')
    sql_cursor.execute('''insert into config values
        ('AuthURL','https://id.twitch.tv/oauth2/validate'),
        ('client_id',''),
        ('client_secret',''),
        ('redirect_uri','')
    ''')
    sql_connection.commit()
    config=read_config()

print(config)

def read_rules():
    allow=sql_cursor.execute('select header,value from rules where allow is true').fetchall()
    deny=sql_cursor.execute('select header,value from rules where allow is false').fetchall()
    return (deny,allow)

try:
    rules=read_rules()
except sql.OperationalError:
    sql_cursor.execute('create table rules(header,value,allow)')
    sql_cursor.execute('''insert into rules values
        ('client_id','.*',true),
        ('user_id','.*',true)
    ''')
    sql_connection.commit()
    rules=read_rules()

print(rules)

read_secrets=lambda:dict(sql_cursor.execute('select * from secrets').fetchall())

try:
    secrets=read_secrets()
except sql.OperationalError:
    sql_cursor.execute('create table secrets(client_id,client_secret)')
    sql_cursor.execute('''insert into secrets values ('exampleid','examplesecret')''')
    sql_connection.commit()
    secrets=read_secrets()

print(secrets)

config={
    'api':config,
    'secrets':secrets,
    'deny':dict(rules[0]),
    'allow':dict(rules[1])
}

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
    if 'broadcaster_id' in config['api'] and config['api']['broadcaster_id']!=response['data'][0]['id']:
        config['api']=read_config()
        return
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
        write_config()
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

def validate(authorization):
    response=urlopen(Request(config['NETWORK']['AuthURL'],headers={
        'Authorization':authorization
    }))
    return json.loads(response.read().decode())

def write_config():
    sql_cursor.execute('begin transaction')
    try:
        sql_cursor.executescript(f'''delete * from config;
            insert into config values
                ('AuthURL','{config['api']['AuthURL']}'),
                ('client_id','{config['api']['client_id']}'),
                ('client_secret','{config['api']['client_secret']}'),
                ('redirect_uri','{config['api']['redirect_uri']}');
        ''')
        if 'broadcaster_id' in config['api']:
            sql_cursor.execute(f'''insert into config values ('broadcaster_id','{config['api']['broadcaster_id']})''')
        if 'refresh_token' in config['api']:
            sql_cursor.execute(f'''insert into config values ('refresh_token','{config['api']['refresh_token']})''')
        if 'access_token' in config['api']:
            sql_cursor.execute(f'''insert into config values ('access_token','{config['api']['access_token']})''')
        sql_cursor.execute('delete * from rules')
        for header,value in config['deny'].items():
            sql_cursor.execute(f'''insert into rules values ('{header}','{value}',false)''')
        for header,value in config['allow'].items():
            sql_cursor.execute(f'''insert into rules values ('{header}','{value}',true)''')
        sql_cursor.execute('delete * from secrets')
        for client_id,secret in config['secrets'].items():
            sql_cursor.execute(f'''insert into secrets values ('{client_id}','{secret}')''')
        sql_cursor.execute('commit')
    except:
        sql_cursor.execute('rollback')

def request_handler(method='GET',path='/',params={},headers={},body='') -> tuple[str,int,dict]:
    global config
    if(method=='OPTIONS'):
        return '',204,{
            'Access-Control-Allow-Headers':'authorization,client-id',
        }
    if(method=='GET'):
        try:
            if path.startswith('/tba.mjs'):
                with open('tba.mjs','r') as tba_script:
                    tba=tba_script.read()
                return tba,200,{
                    'content-type':'text/javascript',
                }
            if path.startswith('/code'):
                get_tokens(params['code'])
                get_broadcaster_id()
                write_config()
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
                response=validate(authorization)
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
            if path.startswith('/config.html'):
                with open('config.html','r') as file:
                    config_page=file.read()
                return config_page,200,{
                    'content-type':'text/html',
                }
            if path.startswith('/config'):
                if 'broadcaster_id' in config['api']:
                    if 'authorization' not in headers:
                        return 'authorization not in headers',401,{
                            'content-type':'text/plain'
                        }
                    if validate(headers['authorization'])['user_id']!=config['api']['broadcaster_id']:
                        return '',403,{}
                if method=='GET':
                    return json.dumps(config),200,{
                        'content-type':'text/json'
                    }
                if method=='POST':
                    config=json.loads(body)
                    write_config()
                    return '',204,{}
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