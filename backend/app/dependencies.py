from fastapi import Depends,HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.core.security import decode_access_token
oauth2_scheme=OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
def get_current_user(token:str=Depends(oauth2_scheme),db:Session=Depends(get_db)):
    try:
        claims=decode_access_token(token); uid=int(claims["sub"])
    except (ValueError,KeyError,TypeError):
        raise HTTPException(401,"Authentification invalide")
    user=db.query(User).filter(User.id==uid,User.is_active.is_(True)).first()
    if user is None or user.company_id!=claims.get("company_id"):
        raise HTTPException(401,"Compte introuvable ou désactivé")
    return user
def require_company_admin(user:User=Depends(get_current_user)):
    if user.role not in {"company_admin","platform_admin"}: raise HTTPException(403,"Droits administrateur requis")
    return user
