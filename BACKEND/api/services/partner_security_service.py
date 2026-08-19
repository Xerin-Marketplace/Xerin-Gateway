import hashlib
import hmac
import ipaddress
import secrets
import time
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.config import settings
from api.deps import get_db
from api.models import PartnerCredential, PartnerIdempotencyRecord, PartnerRequestLog, PartnerRequestNonce


def _vault() -> Fernet:
    key = hashlib.sha256(f"xerin-partner-signing:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(urlsafe_b64encode(key))


def create_credential(db:Session,*,company_id,name,scopes,allowed_cidrs,rate_limit,expires_at,actor_id,rotated_from_id=None):
    normalized=[]
    for value in allowed_cidrs:
        try: normalized.append(str(ipaddress.ip_network(value,strict=False)))
        except ValueError as exc: raise ValueError(f"Invalid CIDR: {value}") from exc
    secret=secrets.token_urlsafe(32)
    row=PartnerCredential(logistics_company_id=company_id,name=name,key_id=f"xerin_{secrets.token_hex(12)}",signing_key_ciphertext=_vault().encrypt(secret.encode()).decode(),
        secret_fingerprint=hashlib.sha256(secret.encode()).hexdigest()[:16],scopes=sorted(set(scopes)),allowed_cidrs=normalized,
        rate_limit_per_minute=rate_limit or settings.PARTNER_DEFAULT_RATE_LIMIT_PER_MINUTE,expires_at=expires_at,created_by_id=actor_id,rotated_from_id=rotated_from_id)
    db.add(row);db.flush();return row,secret


def request_target(request: Request) -> str:
    return request.url.path + (f"?{request.url.query}" if request.url.query else "")


def canonical_request(timestamp,nonce,method,target,body):
    body_hash=hashlib.sha256(body).hexdigest()
    return f"{timestamp}\n{nonce}\n{method.upper()}\n{target}\n{body_hash}".encode(),body_hash


def _source_ip(request): return request.client.host if request.client else ""


def _allowed_ip(ip,cidrs):
    if not cidrs:return True
    try: address=ipaddress.ip_address(ip)
    except ValueError:return False
    return any(address in ipaddress.ip_network(value,strict=False) for value in cidrs)


def _log(db,request,*,credential=None,result,error=None,body_hash=None):
    row=PartnerRequestLog(credential_id=credential.id if credential else None,logistics_company_id=credential.logistics_company_id if credential else None,
        request_id=getattr(request.state,"partner_request_id",str(uuid4())),method=request.method,path=request_target(request),source_ip=_source_ip(request),
        nonce=request.headers.get("X-Xerin-Nonce"),idempotency_key=request.headers.get("Idempotency-Key"),body_sha256=body_hash,auth_result=result,error_code=error)
    db.add(row);db.commit();request.state.partner_request_log_id=row.id;return row


def require_partner_scope(required_scope):
    async def dependency(request:Request,db:Session=Depends(get_db)):
        request.state.partner_request_id=str(uuid4())
        key_id=request.headers.get("X-Xerin-Key");timestamp=request.headers.get("X-Xerin-Timestamp");nonce=request.headers.get("X-Xerin-Nonce");signature=request.headers.get("X-Xerin-Signature")
        credential=db.query(PartnerCredential).filter(PartnerCredential.key_id==key_id).first() if key_id else None
        if not credential:_log(db,request,result="denied",error="unknown_key");raise HTTPException(401,"Invalid partner credentials")
        now=datetime.now(timezone.utc)
        if credential.status!="active" or (credential.expires_at and credential.expires_at<=now):
            _log(db,request,credential=credential,result="denied",error="inactive_key");raise HTTPException(401,"Partner credential is inactive")
        if required_scope not in (credential.scopes or []):
            _log(db,request,credential=credential,result="denied",error="scope_denied");raise HTTPException(403,f"Partner scope required: {required_scope}")
        if not _allowed_ip(_source_ip(request),credential.allowed_cidrs or []):
            _log(db,request,credential=credential,result="denied",error="ip_denied");raise HTTPException(403,"Partner source IP is not allowed")
        if not timestamp or not nonce or not signature or len(nonce)>128:
            _log(db,request,credential=credential,result="denied",error="missing_signature_headers");raise HTTPException(401,"Missing partner signature headers")
        try: timestamp_value=int(timestamp)
        except ValueError:
            _log(db,request,credential=credential,result="denied",error="invalid_timestamp");raise HTTPException(401,"Invalid partner timestamp")
        if abs(int(time.time())-timestamp_value)>settings.PARTNER_SIGNATURE_MAX_SKEW_SECONDS:
            _log(db,request,credential=credential,result="denied",error="stale_timestamp");raise HTTPException(401,"Partner timestamp is outside the allowed window")
        recent=now-timedelta(minutes=1)
        count=db.query(PartnerRequestLog).filter(PartnerRequestLog.credential_id==credential.id,PartnerRequestLog.auth_result=="accepted",PartnerRequestLog.created_at>=recent).count()
        if count>=credential.rate_limit_per_minute:
            _log(db,request,credential=credential,result="denied",error="rate_limited");raise HTTPException(429,"Partner rate limit exceeded")
        body=await request.body();canonical,body_hash=canonical_request(timestamp,nonce,request.method,request_target(request),body)
        try: signing_key=_vault().decrypt(credential.signing_key_ciphertext.encode())
        except InvalidToken:
            _log(db,request,credential=credential,result="denied",error="credential_decryption_failed",body_hash=body_hash);raise HTTPException(401,"Invalid partner credentials")
        expected=hmac.new(signing_key,canonical,hashlib.sha256).hexdigest()
        supplied=signature.removeprefix("sha256=").strip().lower()
        if not hmac.compare_digest(expected,supplied):
            _log(db,request,credential=credential,result="denied",error="invalid_signature",body_hash=body_hash);raise HTTPException(401,"Invalid partner signature")
        db.add(PartnerRequestNonce(credential_id=credential.id,nonce=nonce,expires_at=now+timedelta(seconds=settings.PARTNER_NONCE_TTL_SECONDS)))
        try: db.commit()
        except IntegrityError:
            db.rollback();_log(db,request,credential=credential,result="denied",error="replayed_nonce",body_hash=body_hash);raise HTTPException(409,"Partner nonce has already been used")
        credential.last_used_at=now;credential.last_used_ip=_source_ip(request);_log(db,request,credential=credential,result="accepted",body_hash=body_hash)
        request.state.partner_body_hash=body_hash;return credential
    return dependency


def begin_idempotency(db,*,credential,request,key):
    if not key or len(key)<8:raise HTTPException(400,"Idempotency-Key of at least 8 characters is required")
    existing=db.query(PartnerIdempotencyRecord).filter(PartnerIdempotencyRecord.credential_id==credential.id,PartnerIdempotencyRecord.idempotency_key==key).first()
    if existing:
        if existing.method!=request.method or existing.path!=request_target(request) or existing.request_hash!=request.state.partner_body_hash:raise HTTPException(409,"Idempotency key was reused with a different request")
        if existing.state=="completed":return existing,True
        raise HTTPException(409,"The idempotent request is still processing")
    row=PartnerIdempotencyRecord(credential_id=credential.id,idempotency_key=key,method=request.method,path=request_target(request),request_hash=request.state.partner_body_hash)
    db.add(row);db.flush();return row,False


def complete_idempotency(row,status,body):
    row.state="completed";row.response_status=status;row.response_body=body;row.completed_at=datetime.now(timezone.utc)
