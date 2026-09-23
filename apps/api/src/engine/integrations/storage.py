"""MinIO/S3 integratsiyasi — barcha binary aktivlar (audio/rasm/depth/video/kadr)
shu modul orqali yoziladi va o'qiladi. Boshqa kod boto3'ni to'g'ridan-to'g'ri chaqirmaydi.

``boto3`` sinxron, shuning uchun har bir chaqiriq ``asyncio.to_thread`` ichida ishlaydi.

Test uchun (``moto.mock_aws``): ``settings.s3_endpoint`` bo'sh qatorga o'rnatilsa,
klient standart AWS endpoint'iga ulanadi va moto uni ushlab qoladi — custom
(``http://localhost:9000`` kabi) endpoint'ni moto odatda intercept qilmaydi.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Literal

import boto3
import httpx
from botocore.exceptions import ClientError

from engine.settings import settings

Kind = Literal["audio", "image", "depth", "video", "frame"]


def _client():
    """Joriy ``settings`` asosida yangi boto3 S3 klient. Har chaqiriqda qayta
    o'qiladi — testlarda ``settings.s3_endpoint``ni monkeypatch qilish yetarli."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )


def _http_client() -> httpx.AsyncClient:
    """Test uchun alohida funksiya — ``monkeypatch.setattr(storage, "_http_client", ...)``."""
    return httpx.AsyncClient()


def key_for(workspace_id: str, kind: Kind, ext: str) -> str:
    """``ws/{workspace_id}/{kind}/{uuid}.{ext}`` — barcha aktiv kalitlari shu shaklda."""
    return f"ws/{workspace_id}/{kind}/{uuid.uuid4()}.{ext}"


async def ensure_bucket() -> None:
    """Bucket mavjud emasligini tekshiradi va kerak bo'lsa yaratadi (idempotent)."""

    def _do() -> None:
        client = _client()
        try:
            client.head_bucket(Bucket=settings.s3_bucket)
        except ClientError:
            client.create_bucket(Bucket=settings.s3_bucket)

    await asyncio.to_thread(_do)


async def put_bytes(key: str, data: bytes, content_type: str) -> str:
    """Baytlarni yozadi va ``s3://bucket/key`` URI qaytaradi."""

    def _do() -> None:
        _client().put_object(
            Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type
        )

    await asyncio.to_thread(_do)
    return f"s3://{settings.s3_bucket}/{key}"


async def put_file(key: str, path: str, content_type: str) -> str:
    """Lokal fayldan yozadi (masalan, Remotion render natijasi) va ``s3://`` URI qaytaradi."""

    def _do() -> None:
        _client().upload_file(
            path, settings.s3_bucket, key, ExtraArgs={"ContentType": content_type}
        )

    await asyncio.to_thread(_do)
    return f"s3://{settings.s3_bucket}/{key}"


async def get_bytes(key: str) -> bytes:
    """Obyektni to'liq baytlar sifatida o'qiydi."""

    def _do() -> bytes:
        obj = _client().get_object(Bucket=settings.s3_bucket, Key=key)
        return obj["Body"].read()

    return await asyncio.to_thread(_do)


async def presigned_url(key: str, expires: int = 3600) -> str:
    """Vaqtinchalik yuklab olish havolasi (ichki/administrativ foydalanish uchun)."""

    def _do() -> str:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires,
        )

    return await asyncio.to_thread(_do)


def public_url(uri_or_key: str) -> str:
    """``s3://bucket/key`` yoki bare ``key``ni brauzerda ko'rinadigan URL'ga aylantiradi
    (``{public_s3_url}/{bucket}/{key}``)."""
    if uri_or_key.startswith("s3://"):
        rest = uri_or_key[len("s3://"):]
        bucket, _, key = rest.partition("/")
    else:
        bucket, key = settings.s3_bucket, uri_or_key
    base = settings.public_s3_url.rstrip("/")
    return f"{base}/{bucket}/{key}"


async def download_to_storage(url: str, key: str, content_type: str | None = None) -> str:
    """Tashqi URL'dan (fal.ai, TTS provayder va h.k.) yuklab olib MinIO'ga yozadi."""
    async with _http_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        ctype = content_type or resp.headers.get("content-type", "application/octet-stream")
        return await put_bytes(key, resp.content, ctype)
