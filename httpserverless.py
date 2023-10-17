try:
    from http.server import ThreadingHTTPServer as HTTPServer
except ImportError:
    from http.server import HTTPServer

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlencode,parse_qsl,urlparse

def request(method='GET',path='/',params={},headers={},body='') -> tuple[str,int,dict]:
        return f'''
        Hello World!
        method={method}
        path={path}
        params={params}
        headers:
        {headers}
        body:
        {body}
        ''',200,{}

class ServerlessRequestHandler(BaseHTTPRequestHandler):
    def handle_serverless_request(self):
        method=self.requestline.split(' ')[0]
        path=urlparse(self.path)
        params=dict(parse_qsl(path.query))
        path=path.path
        bodylen=0
        if(self.headers['content-length']):
            bodylen=int(self.headers['content-length'])
        body,code,headers=request(method,path,params,self.headers,self.rfile.read(bodylen).decode())
        self.send_response(code)
        for key,val in headers.items():
            self.send_header(key,val)
        body=body.encode()
        self.send_header('Content-Length',len(body))
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(body)
    do_GET=handle_serverless_request
    do_POST=handle_serverless_request
    do_HEAD=handle_serverless_request
    do_PUT=handle_serverless_request
    do_DELETE=handle_serverless_request
    do_PATCH=handle_serverless_request
    do_TRACE=handle_serverless_request
    do_CONNECT=handle_serverless_request

def start_server(request_handler):
    global request
    request=request_handler
    HTTPServer(('0.0.0.0',5000),ServerlessRequestHandler).serve_forever()

if __name__ == '__main__':
    start_server(request)