import * as Crypto from 'expo-crypto';
import {buildURL} from './core.ts';
export const AUTH_CALLBACK='org.daynomy.app://auth/callback';
export type NativeAuthAttempt={url:string;verifier:string;state:string};
function validateVerifier(value:string) {if(!/^[A-Za-z0-9._~-]{43,128}$/.test(value))throw new Error('로그인 검증 정보를 확인해 주세요.');}
function urlBase64(bytes:Uint8Array):string {
  const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';let text='';
  for(let i=0;i<bytes.length;i+=3){const a=bytes[i]!,b=bytes[i+1],c=bytes[i+2];text+=alphabet[a>>2]+alphabet[((a&3)<<4)|((b??0)>>4)];if(b!==undefined)text+=alphabet[((b&15)<<2)|((c??0)>>6)];if(c!==undefined)text+=alphabet[c&63];}
  return text;
}
export async function createNativeAuth(baseURL:string):Promise<NativeAuthAttempt> {
  const verifier=urlBase64(await Crypto.getRandomBytesAsync(32));const state=urlBase64(await Crypto.getRandomBytesAsync(32));
  validateVerifier(verifier);
  const digest=await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256,verifier,{encoding:Crypto.CryptoEncoding.HEX});
  const challenge=urlBase64(Uint8Array.from(digest.match(/.{2}/g)!.map(pair=>parseInt(pair,16))));
  buildURL(baseURL,'/');
  const url=new URL(baseURL);
  if(url.username||url.password||!['http:','https:'].includes(url.protocol))throw new Error('API 주소를 확인해 주세요.');
  url.pathname='/api/auth/mobile/start';url.search='';url.hash='';url.searchParams.set('code_challenge',challenge);url.searchParams.set('state',state);
  return {url:url.toString(),verifier,state};
}
export function validateNativeCallback(callback:string,attempt:NativeAuthAttempt):{code:string;codeVerifier:string} {
  validateVerifier(attempt.verifier);
  if(!/^[A-Za-z0-9_-]{32,128}$/.test(attempt.state))throw new Error('로그인 상태를 확인해 주세요.');
  const url=new URL(callback);
  if(url.protocol!=='org.daynomy.app:'||url.hostname!=='auth'||url.pathname!=='/callback'||url.username||url.password||url.port||url.hash||url.searchParams.has('error')||url.searchParams.getAll('state').length!==1||url.searchParams.get('state')!==attempt.state||url.searchParams.getAll('code').length!==1||!url.searchParams.get('code'))throw new Error('로그인 응답을 확인하지 못했어요. 다시 로그인해 주세요.');
  return {code:url.searchParams.get('code')!,codeVerifier:attempt.verifier};
}
