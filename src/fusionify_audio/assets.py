"""Bounded local media registration and allowlisted, IP-pinned HTTPS imports."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote

from PIL import Image
from .engine import DEMUXERS, MAX_BYTES, MAX_SECONDS, checked_run

IMAGE_FORMATS = {'.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG','.webp':'WEBP'}
SUFFIXES = set(DEMUXERS) | set(IMAGE_FORMATS) | {'.mp4','.mov'}


def local_media(root: Path, value: str) -> Path:
    root = root.resolve(strict=True)
    requested = Path(value).expanduser()
    path = (requested if requested.is_absolute() else root/requested).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Media must be a regular file inside FAI_MEDIA_ROOT.')
    if path.suffix.lower() not in SUFFIXES:
        raise ValueError('Unsupported media extension.')
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError('Media must be nonempty and at most 64 MiB.')
    return path


def inspect_media(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix in IMAGE_FORMATS:
        with Image.open(path) as im:
            if im.format != IMAGE_FORMATS[suffix]:
                raise ValueError('Image content does not match its extension.')
            if im.width*im.height > 24_000_000:
                raise ValueError('Images are limited to 24 megapixels.')
            metadata = {'width':im.width,'height':im.height}
            im.verify()
        kind = 'image'
    else:
        demuxer = 'mov' if suffix in {'.mp4','.mov'} else DEMUXERS[suffix]
        probe = json.loads(checked_run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-f',demuxer,
                                      '-show_entries','format=duration:stream=codec_type,width,height,sample_rate,channels',
                                      '-of','json',str(path)]))
        duration = float(probe.get('format',{}).get('duration',0))
        if not 0 < duration <= MAX_SECONDS:
            raise ValueError('Media duration must be positive and at most 180 seconds.')
        video = next((s for s in probe['streams'] if s.get('codec_type')=='video'),None)
        kind = 'video' if suffix in {'.mp4','.mov'} and video else 'audio'
        if suffix in {'.mp4','.mov'} and video is None:
            raise ValueError('The video file contains no video stream.')
        metadata = {'duration_s':duration}
        if video:
            if video.get('width',0)*video.get('height',0) > 16_777_216:
                raise ValueError('Video frames are limited to 16 megapixels.')
            metadata.update(width=video.get('width'),height=video.get('height'))
    return {'kind':kind,'metadata':metadata,'bytes':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_remote(url: str, hosts: set[str]) -> tuple[object, str]:
    if len(url)>4096 or any(ord(c)<33 for c in url):
        raise ValueError('Invalid URL.')
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower().rstrip('.')
    if parsed.scheme!='https' or not host or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None,443):
        raise ValueError('Use a direct HTTPS file URL on port 443 without userinfo or fragment.')
    if host not in hosts:
        raise ValueError('This hostname is not in FAI_IMPORT_HOSTS.')
    # Resolve once, reject the whole answer if any destination is non-public,
    # then pin the connection while retaining TLS hostname verification.
    addresses = sorted({item[4][0] for item in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError('URL resolves to a private, loopback, link-local or reserved address.')
    return parsed, addresses[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str):
        super().__init__(host,port=443,timeout=20,context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address,443),self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock,server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def download_file(url: str, root: Path, hosts: set[str]) -> Path:
    if not hosts: raise ValueError('URL imports are disabled until FAI_IMPORT_HOSTS is configured.')
    target = None
    started=time.monotonic()
    try:
        for attempt in range(4):
            parsed,address = validate_remote(url,hosts)
            conn = PinnedHTTPS(parsed.hostname,address)
            try:
                request_path = parsed.path or '/'
                if parsed.query: request_path += '?'+parsed.query
                conn.request('GET',request_path,headers={'User-Agent':'Fusionify-Audio/0.4','Accept':'*/*'})
                response = conn.getresponse()
                if response.status in (301,302,303,307,308):
                    location=response.getheader('Location')
                    if not location or attempt==3: raise ValueError('Too many or invalid redirects.')
                    url=urljoin(url,location)
                    continue
                if response.status!=200: raise ValueError('Remote file request failed.')
                suffix=Path(unquote(parsed.path)).suffix.lower()
                if suffix not in SUFFIXES: raise ValueError('URL must end in a supported media extension.')
                length=response.getheader('Content-Length')
                if length and (not length.isdecimal() or int(length)>MAX_BYTES):
                    raise ValueError('Remote media exceeds 64 MiB or has an invalid size.')
                target=root/f'{uuid.uuid4().hex}{suffix}'
                total=0
                with target.open('xb') as out:
                    while chunk:=response.read(65536):
                        if time.monotonic()-started>60:raise ValueError('Remote import timed out.')
                        total+=len(chunk)
                        if total>MAX_BYTES: raise ValueError('Remote media exceeds 64 MiB.')
                        out.write(chunk)
                return target
            finally:
                conn.close()
        raise ValueError('Import failed.')
    except BaseException:
        if target: target.unlink(missing_ok=True)
        raise
