from os import environ
configPath=environ.get('TBA_CONFIG_PATH','tba.ini')
print('configPath =',configPath)
from configparser import ConfigParser
config=ConfigParser()
try:
    with open(configPath,'r') as configFile:
        config.read_file(configFile)
except:
    print('error reading config, creating default')
    with open(configPath,'w') as configFile:
        config['NETWORK']={
            'IP':'localhost',
            'Port':5000,
            'AuthURL':'https://id.twitch.tv/oauth2/validate'
        }
        config['DENY']={}
        config['ALLOW']={
            'client_id':'.*',
            'user_id':'.*'
        }
        config['LOG']={
            'authorization':False,
            'response':True,
            'status':True
        }
        config.write(configFile)

print('config loaded, initializing server')
from advancedhttpserver import AdvancedHTTPServer, RequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError
from threading import Thread
import json,re
class TBA(RequestHandler):
    def do_GET(self):
        try:
            authorization=self.headers.get('Authorization')
            response=urlopen(Request(config['NETWORK']['AuthURL'],headers={
                'Authorization':authorization
            }))
        except URLError as error:
            response=error
        except Exception as exception:
            self.send_error(500,str(exception))
            return
        finally:
            if(response.code!=200):
                self.send_error(response.code)
                print(authorization,response.read().decode())
            else:
                response=json.loads(response.read().decode())
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
            self.end_headers()
            log=[]
            if(bool(config['LOG']['authorization'])):
                log.append(authorization)
            if(bool(config['LOG']['response'])):
                log.append(response)
            if(bool(config['LOG']['status'])):
                log.append(status)
            print(*log)

server=AdvancedHTTPServer(TBA,(config['NETWORK']['IP'],int(config['NETWORK']['Port'])))
server=Thread(target=server.serve_forever)
server.start()

try:
    from subprocess import run
    print('startup complete, attempting systemd-notify')
    run(['systemd-notify','--ready'])
except Exception as e:
    print(str(e))
finally:
    print('awaiting requests')
    server.join()