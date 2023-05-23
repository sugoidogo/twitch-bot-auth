export function request_auth(client_id,scope,redirect_uri=location.origin+location.pathname){
    const url=new URL('https://id.twitch.tv/oauth2/authorize')
    url.search=new URLSearchParams({
        client_id:client_id,
        response_type:'code',
        scope:scope
    })
    if(window.confirm('redirecting you to twitch for authorization')){
        location.assign(url.href+'&redirect_uri='+redirect_uri)
    }
}

export function get_url_params(){
    return Object.fromEntries(new URLSearchParams(location.search))
}

export function fetch_tokens(client_id,code,redirect_uri=location.origin+location.path){
    const url=new URL('/oauth2/token',import.meta.url)
    url.search=new URLSearchParams({
        client_id:client_id,
        code:code,
        grant_type:'authorization_code',
        redirect_uri:redirect_uri
    })
    return fetch(url.href)
    .then(response=>response.json())
}

export function validate_tokens(tokens){
    const url=new URL('/',import.meta.url)
    return fetch(url,{headers:{
        'Authorization':'OAuth '+tokens.access_token
    }}).then(response=>response.json())
    .then(validation=>{
        if('message' in validation){
            throw new Error(validation.message)
        }
        Object.assign(tokens,validation)
        delete tokens.scope
        return tokens
    })
}

export function set_local_tokens(client_id,tokens){
    localStorage.setItem(client_id,JSON.stringify(tokens))
    return tokens
}

export function get_local_tokens(client_id){
    return JSON.parse(localStorage.getItem(client_id))
}

export function refresh_tokens(refresh_token){
    const url=new URL('/',import.meta.url)
    url.search=new URLSearchParams({
        client_id:client_id,
        grant_type:'refresh_token',
        refresh_token:refresh_token
    })
    return fetch(url.href).then(response=>response.json())
}

export default function get_tokens(client_id,scope,redirect_uri=location.origin+location.pathname){
    let tokens=get_local_tokens(client_id)||get_url_params()
    if('access_token' in tokens){
        return validate_tokens(tokens)
        .catch((error)=>{
            console.warn(error)
            refresh_tokens(tokens.refresh_token)
        })
        .then(validate_tokens)
        .then(tokens=>set_local_tokens(client_id,tokens))
    }
    return fetch_tokens(client_id,tokens.code,redirect_uri)
    .then(validate_tokens)
    .then(tokens=>set_local_tokens(client_id,tokens))
    .catch((error)=>{
            console.warn(error)
            request_auth(client_id,scope,redirect_uri)
        })    
}