"""Authenticated single-owner HTTP MCP, uploads, and short-lived artifacts."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote, urlsplit

from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route

from .assets import SUFFIXES
from .engine import MAX_BYTES
from .server import build_server, project_summary
from .service import Service
from .store import identifier


class ArtifactSigner:
    def __init__(self, key: str, base_url: str):
        if not 32<=len(key)<=256 or not key.isascii() or any(c.isspace() for c in key):
            raise ValueError('FAI_API_TOKEN must contain 32 to 256 ASCII characters without whitespace.')
        parsed=urlsplit(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise ValueError('FAI_PUBLIC_BASE_URL must be an origin without path, credentials or query.')
        if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1')):
            raise ValueError('Use HTTPS for public deployment, or HTTP on loopback for local testing.')
        if not parsed.hostname:raise ValueError('Public base URL requires a hostname.')
        self.key=hashlib.sha256(('fai-artifacts:'+key).encode()).digest()
        self.base_url=base_url.rstrip('/')

    def signature(self, artifact_id: str, suffix: str, expires: int) -> str:
        identifier(artifact_id)
        if suffix not in ('mp4','json','csv','mp3','svg'):raise ValueError('Invalid artifact type.')
        return hmac.new(self.key,f'{artifact_id}.{suffix}:{expires}'.encode(),hashlib.sha256).hexdigest()

    def link(self, artifact_id: str, suffix: str) -> str:
        expires=int(time.time())+600
        return f'{self.base_url}/downloads/{artifact_id}.{suffix}?expires={expires}&signature={self.signature(artifact_id,suffix,expires)}'

    def verify(self, artifact_id: str, suffix: str, expires: str, signature: str) -> bool:
        try:
            value=int(expires)
            if not int(time.time())<=value<=int(time.time())+900:return False
            return hmac.compare_digest(self.signature(artifact_id,suffix,value),signature)
        except (ValueError,TypeError):return False


class AccessBoundary:
    """Pure ASGI middleware so streaming MCP responses keep their transport semantics."""
    def __init__(self, app, token: str, origin: str):
        self.app,self.token,self.origin=app,token,origin

    async def __call__(self, scope, receive, send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers={k.lower():v for k,v in scope['headers']}
        path=scope.get('path','')
        if path.startswith('/api/') or path=='/mcp' or path.startswith('/mcp/'):
            value=headers.get(b'authorization',b'')
            expected=('Bearer '+self.token).encode('ascii')
            if not secrets.compare_digest(value,expected):
                response=JSONResponse({'error':'Authentication required.'},status_code=401,headers={'WWW-Authenticate':'Bearer'})
                return await response(scope,receive,send)
            origin=headers.get(b'origin',b'').decode('latin1')
            if origin and origin!=self.origin:
                return await JSONResponse({'error':'Origin denied.'},status_code=403)(scope,receive,send)
        async def secure_send(message):
            if message['type']=='http.response.start':
                message['headers']=list(message.get('headers',[]))+[
                    (b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer'),
                    (b'cache-control',b'no-store'),(b'x-frame-options',b'DENY'),
                    (b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")]
            await send(message)
        await self.app(scope,receive,secure_send)


async def json_body(request: Request) -> dict:
    data=bytearray()
    async with asyncio.timeout(30):
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>262144:raise ValueError('JSON request exceeds 256 KiB.')
    value=json.loads(data)
    if not isinstance(value,dict):raise ValueError('Expected a JSON object.')
    return value


def build_http_app(service: Service, token: str, public_base_url: str):
    signer=ArtifactSigner(token,public_base_url)
    origin=signer.base_url
    parsed=urlsplit(origin);hostname=parsed.hostname
    service.artifact_url=signer.link
    service.upload_url=origin+'/'
    mcp=build_server(service,http=True,
                     allowed_hosts=[hostname,hostname+':*'],allowed_origins=[origin])
    mcp_app=mcp.streamable_http_app()
    upload_slots=asyncio.Semaphore(2)
    api_slots=asyncio.Semaphore(2)
    web=Path(__file__).parent/'web'

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():yield

    async def index(request):return FileResponse(web/'index.html',media_type='text/html')

    async def static(request):
        filename=request.path_params['filename']
        if filename not in ('app.js','app.css'):return Response(status_code=404)
        return FileResponse(web/filename,media_type='text/javascript' if filename.endswith('.js') else 'text/css')

    async def health(request):return JSONResponse({'status':'ok','version':'0.4.0'})

    async def upload(request: Request):
        filename=unquote(request.headers.get('x-filename',''))
        suffix=Path(filename).suffix.lower()
        if not filename or len(filename)>160 or '/' in filename or '\\' in filename or suffix not in SUFFIXES:
            return JSONResponse({'error':'Supply a supported file name in X-Filename.'},status_code=400)
        length=request.headers.get('content-length')
        if length and (not length.isdecimal() or int(length)>MAX_BYTES):
            return JSONResponse({'error':'Upload exceeds 64 MiB.'},status_code=413)
        folder=service.media_root/'uploads';folder.mkdir(exist_ok=True)
        if not folder.resolve().is_relative_to(service.media_root):return Response(status_code=400)
        path=folder/f'{uuid.uuid4().hex}{suffix}'
        total=0
        try:
            async with upload_slots, asyncio.timeout(90):
                with path.open('xb') as out:
                    async for chunk in request.stream():
                        total+=len(chunk)
                        if total>MAX_BYTES:raise ValueError('Upload exceeds 64 MiB.')
                        out.write(chunk)
                result=await asyncio.to_thread(service.register_asset,str(path),filename)
            return JSONResponse(result,status_code=201)
        except (ValueError,OSError,TimeoutError):
            path.unlink(missing_ok=True)
            return JSONResponse({'error':'Upload failed validation, exceeded its size, or timed out.'},status_code=400)

    operations={
        'get_workspace':lambda **kw:service.workspace(),
        'list_media_assets':lambda **kw:{'assets':service.assets(**kw)},
        'analyze_audio':service.analyze,'get_audio_profile':service.profile,
        'get_audio_timeline':service.timeline,'correct_beat_markers':service.correct_beats,
        'create_music_direction':service.music_direction,
        'get_rhythm_review':service.rhythm_review,'estimate_tap_tempo':service.tap_tempo,
        'apply_tempo_map':service.apply_tempo_map,
        'import_media_url':service.import_url,
        'create_video_project':lambda **kw:project_summary(service.create_project(**kw)),
        'get_video_project':lambda **kw:project_summary(service.project(**kw)),
        'review_content_fit':service.content_fit,
        'revise_video_project':lambda **kw:project_summary(service.revise_project(**kw)),
        'render_video_project':service.render_project,'render_visualizer':service.render,
        'get_job_status':service.status,'cancel_render_job':service.cancel_job,
        'export_video_timeline':service.export,
        'list_video_projects':lambda **kw:{'projects':service.list_projects(**kw)},
        'list_render_jobs':lambda **kw:{'jobs':service.list_jobs(**kw)},
        'render_beat_preview':service.beat_preview,'export_audio_analysis':service.export_analysis,
    }

    async def call(request: Request):
        try:
            body=await json_body(request)
            operation=body.get('operation');arguments=body.get('arguments',{})
            if operation not in operations or not isinstance(arguments,dict):raise ValueError('Unknown operation or arguments.')
            async with api_slots:
                result=await asyncio.to_thread(operations[operation],**arguments)
            return JSONResponse(result)
        except (ValueError,TypeError,OSError,TimeoutError) as exc:
            # Do not echo arbitrary filesystem paths or credential-bearing URLs.
            message=str(exc) if isinstance(exc,ValueError) else 'Invalid request or unavailable media.'
            return JSONResponse({'error':message[:1000]},status_code=400)

    async def download(request: Request):
        artifact_id=request.path_params['artifact_id'];suffix=request.path_params['suffix']
        if not signer.verify(artifact_id,suffix,request.query_params.get('expires',''),request.query_params.get('signature','')):
            return JSONResponse({'error':'Invalid or expired download link.'},status_code=403)
        try:path=service.artifact_path(artifact_id,suffix)
        except (ValueError,OSError):return Response(status_code=404)
        types={'mp4':'video/mp4','json':'application/json','csv':'text/csv','mp3':'audio/mpeg','svg':'image/svg+xml'}
        return FileResponse(path,media_type=types[suffix],filename=f'fusionify-{artifact_id}.{suffix}',content_disposition_type='inline' if suffix in ('mp4','mp3') else 'attachment')

    app=Starlette(routes=[Route('/',index),Route('/favicon.ico',lambda request:Response(status_code=204)),Route('/static/{filename}',static),Route('/healthz',health),
                          Route('/api/upload',upload,methods=['POST']),Route('/api/call',call,methods=['POST']),
                          Route('/downloads/{artifact_id}.{suffix}',download),Mount('/',app=mcp_app)],lifespan=lifespan)
    return TrustedHostMiddleware(AccessBoundary(app,token,origin),allowed_hosts=[hostname])
