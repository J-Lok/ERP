import time

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create the MinIO/S3 media bucket if it doesn't exist yet. No-op if MinIO isn't configured."""

    help = 'Ensure the configured MinIO/S3 media bucket exists.'

    MAX_ATTEMPTS = 10
    RETRY_DELAY_SECONDS = 2

    def handle(self, *args, **options):
        if not getattr(settings, 'MINIO_ENDPOINT', '') or not all([
            settings.MINIO_ACCESS_KEY, settings.MINIO_SECRET_KEY
        ]):
            self.stdout.write('MinIO not configured, skipping bucket check.')
            return

        import boto3
        from botocore.exceptions import ClientError, EndpointConnectionError

        client = boto3.client(
            's3',
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
        )
        bucket = settings.MINIO_BUCKET_NAME

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                client.head_bucket(Bucket=bucket)
                self.stdout.write(f'Bucket "{bucket}" already exists.')
                return
            except ClientError:
                client.create_bucket(Bucket=bucket)
                self.stdout.write(self.style.SUCCESS(f'Created bucket "{bucket}".'))
                return
            except EndpointConnectionError:
                if attempt == self.MAX_ATTEMPTS:
                    raise
                self.stdout.write(f'MinIO not reachable yet (attempt {attempt}/{self.MAX_ATTEMPTS}), retrying...')
                time.sleep(self.RETRY_DELAY_SECONDS)
