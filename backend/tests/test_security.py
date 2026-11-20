from app.core.security import hash_password,verify_password,create_access_token,decode_access_token
def test_password_hash_is_verified():
    hashed=hash_password("Correct-Horse-Battery-42")
    assert verify_password("Correct-Horse-Battery-42",hashed)
    assert not verify_password("wrong-password",hashed)
def test_token_contains_tenant_claims():
    token=create_access_token(user_id=7,company_id=3,role="company_admin")
    claims=decode_access_token(token)
    assert claims["sub"]=="7" and claims["company_id"]==3
