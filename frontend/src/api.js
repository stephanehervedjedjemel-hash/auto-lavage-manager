const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export function getToken(){return localStorage.getItem('alm_token')}
export function saveToken(token){localStorage.setItem('alm_token',token)}
export function clearToken(){localStorage.removeItem('alm_token')}
export async function api(path,{method='GET',body,auth=true}={}){
  const headers={'Content-Type':'application/json'}
  if(auth && getToken()) headers.Authorization='Bearer '+getToken()
  const response=await fetch(API_URL+path,{method,headers,body:body?JSON.stringify(body):undefined})
  const data=await response.json().catch(()=>({detail:'Réponse serveur illisible'}))
  if(!response.ok) throw new Error(data.detail || 'Une erreur est survenue')
  return data
}
