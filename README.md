# Twitch Bot Auth
This is an http access control system using data from twitch's [Token Validation Endpoint](https://dev.twitch.tv/docs/authentication/validate-tokens), designed for use with the [Nginx auth_request module](https://nginx.org/en/docs/http/ngx_http_auth_request_module.html).
## Setup
Clone or download this repo, and run `pip install -r requirements.txt`, adding arguments to that command as appropriate. For example, to install user modules instead of system modules, add `--user`, or to install modules for this script only, use `--target ./`
## Config
On first run, `tba.ini` will be written with the default config. You will want to edit this config file before deploying to production.
### Network
- `IP`: the bind address for the webserver. Use `0.0.0.0` to bind to all interfaces, or leave the default of `locahost` to only allow connections from the same machine.
- `Port`: port number to bind to. Pick any free port.
- `AuthURL`: the Twitch API (or other compatible api) endpont to use for authorization
### Deny / Allow
Each key is matched to keys in the json data returned from the api endpoint, with each value being a regex string used to match the allow or deny condition.
### Log
these boolean values determine what gets logged for each request.
- `authorization`: the authorization header sent by the client. **Don't enable this in production unless you want responsibility for leaked access tokens.**
- `response`: the response from the upstream authorization endpoint
- `status`: the decision made by TBA, including the reason
## Usage
This endpoint is useful for hosting a public http server whos usage should be restricted to specific twitch bots or users of said bots, or if you want to use the authorization response data, but can only do so via headers, like in the case of the [Nginx auth_request module](https://nginx.org/en/docs/http/ngx_http_auth_request_module.html). If you just want to authorize twitch bot access tokens, you can use the twitch endpoint directly: `auth_request https://id.twitch.tv/oauth2/validate`. Once this server gets a response from the upstream authorization endpoint, Deny patterns are processed first, then Allow patterns. If no patterns match, or a Deny pattern matches, the server returns `403`. If no Deny pattern matches and an Allow pattern matches, the server returns `200`. In all scenarios, the json data returned by the upstream authorization server is converted to headers for use by the downstream web server.