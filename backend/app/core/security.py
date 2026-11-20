import base64, hashlib, hmac, json, secrets, time
from app.core.config import settings
def enc(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def dec(s): return base64.urlsafe_b64decode(s+"="*(-len(s)%4))
def hash_password(password):
    salt=secrets.token_bytes(16); digest=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1)
    return "scrypt$"+enc(salt)+"$"+enc(digest)
def verify_password(password, stored):
    try:
        scheme,salt,digest=stored.split("$",2)
        actual=hashlib.scrypt(password.encode(),salt=dec(salt),n=2**14,r=8,p=1)
        return scheme=="scrypt" and hmac.compare_digest(actual,dec(digest))
    except (ValueError,TypeError): return False
def create_access_token(*,user_id,company_id,role):
    now=int(time.time())
    header=enc(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")).encode())
    payload=enc(json.dumps({"sub":str(user_id),"company_id":company_id,"role":role,"iat":now,
      "exp":now+settings.jwt_expiration_minutes*60},separators=(",",":")).encode())
    message=header+"."+payload
    signature=enc(hmac.new(settings.jwt_secret.encode(),message.encode(),hashlib.sha256).digest())
    return message+"."+signature
def decode_access_token(token):
    try:
        header,payload,signature=token.split(".")
        if json.loads(dec(header)).get("alg")!="HS256": raise ValueError()
        message=header+"."+payload
        expected=enc(hmac.new(settings.jwt_secret.encode(),message.encode(),hashlib.sha256).digest())
        if not hmac.compare_digest(signature,expected): raise ValueError()
        claims=json.loads(dec(payload))
        if int(claims.get("exp",0))<=int(time.time()): raise ValueError()
        return claims
    except (ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        raise ValueError("Jeton invalide ou expiré") from exc
