from minio import Minio
from minio.error import S3Error
import io
import os
import json
import hashlib
import re
from time import sleep
from astrodash.shared.log import get_logger

logger = get_logger(__name__)


class ObjectStore:
    def __init__(self, conf: dict = {}, create_bucket: bool = False) -> None:
        '''Initialize S3 client'''
        self.config = {
            'endpoint-url': os.getenv("ASTRODASH_S3_ENDPOINT_URL", ""),
            'region-name': os.getenv("ASTRODASH_S3_REGION_NAME", ""),
            'aws_access_key_id': os.getenv("ASTRODASH_S3_ACCESS_KEY_ID", ""),
            'aws_secret_access_key': os.getenv("ASTRODASH_S3_SECRET_ACCESS_KEY", ""),
            'bucket': os.getenv("ASTRODASH_S3_BUCKET", ""),
        }
        # Override default config values with input dict
        for key, val in conf.items():
            self.config[key] = val
        self.bucket = self.config['bucket']
        self.client = None
        # If endpoint URL is empty, do not attempt to initialize a client
        if not self.config['endpoint-url']:
            return
        if self.config['endpoint-url'].find('http://') != -1:
            secure = False
            endpoint = self.config['endpoint-url'].replace('http://', '')
        elif self.config['endpoint-url'].find('https://') != -1:
            secure = True
            endpoint = self.config['endpoint-url'].replace('https://', '')
        else:
            logger.error('endpoint URL must begin with http:// or https://')
            return

        self.client = Minio(
            endpoint=endpoint,
            access_key=self.config['aws_access_key_id'],
            secret_key=self.config['aws_secret_access_key'],
            region=self.config['region-name'],
            secure=secure,
        )
        if create_bucket:
            self._initialize_bucket()
        self.part_size = 10 * 1024 * 1024

    def _initialize_bucket(self):
        bucket_name = self.bucket
        found = self.client.bucket_exists(bucket_name)
        if not found:
            self.client.make_bucket(bucket_name)

    def put_object(self, path="", data="", file_path="", json_output=True):
        path = path.strip('/')
        if data:
            logger.debug(f'''Uploading data object to object store: "{path}"''')
            if json_output:
                body = json.dumps(data, indent=2)
            else:
                body = data
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=path,
                data=io.BytesIO(body.encode('utf-8')),
                length=-1,
                part_size=self.part_size)
        elif file_path:
            logger.debug(f'''Uploading file to object store: "{path}"''')
            self.client.fput_object(bucket_name=self.bucket, object_name=path, file_path=file_path)

    def get_object(self, path=""):
        try:
            key = path.strip('/')
            response = self.client.get_object(
                bucket_name=self.bucket,
                object_name=key)
        finally:
            obj = response.data
            response.close()
            response.release_conn()
        return obj

    def stream_object(self, path=""):
        key = path.strip('/')
        response = self.client.get_object(
            bucket_name=self.bucket,
            object_name=key)
        return response.stream(32 * 1024)

    def download_object(self, path="", file_path="", version_id="", max_retries=5):
        path = path.strip('/')
        kwargs = {
            'bucket_name': self.bucket,
            'object_name': path,
            'file_path': file_path,
        }
        if version_id:
            kwargs['version_id'] = version_id
        num_retries = 0
        while num_retries < max_retries:
            try:
                self.client.fget_object(**kwargs)
            except FileNotFoundError as err:
                logger.warning(f'Retrying download after error: {err}')
                num_retries += 1
                sleep(1)
            else:
                return
        raise FileNotFoundError

    def object_info(self, path):
        path = path.strip('/')
        try:
            response = self.client.stat_object(
                bucket_name=self.bucket,
                object_name=path)
            return response
        except S3Error:
            return None
        except Exception as err:
            logger.error(f'''Error fetching object info for key "{path}": {err}''')
            raise

    def object_exists(self, path):
        if self.object_info(path):
            return True
        else:
            return False

    def list_directory(self, root_path, recursive=True):
        objects = self.client.list_objects(
            bucket_name=self.bucket,
            prefix=root_path,
            recursive=recursive,
        )
        return [obj.object_name for obj in objects]

    def get_directory_objects(self, root_path):
        objects = self.client.list_objects(
            bucket_name=self.bucket,
            prefix=root_path,
            include_version=True,
            recursive=True,
        )
        return [obj for obj in objects]

    def md5_checksum(self, file_path):
        '''https://stackoverflow.com/a/58239738'''
        m = hashlib.md5()
        with open(file_path, 'rb') as fh:
            for data in iter(lambda: fh.read(1024 * 1024), b''):
                m.update(data)
        hexdigest = m.hexdigest()
        logger.debug(f'calculated md5 checksum: {hexdigest}')
        return hexdigest

    def etag_checksum(self, file_path, etag_parts=1, file_size=0):
        '''https://stackoverflow.com/a/58239738'''
        md5s = []
        min_chunk_size = 16 * 1024**2
        chunk_size = int(file_size / etag_parts)
        if etag_parts == 1:
            chunk_size = file_size
        elif chunk_size < min_chunk_size:
            chunk_size = min_chunk_size
        chunk_size_mib = int(chunk_size / 1024**2)
        file_size_mib = int(file_size / 1024**2)
        logger.debug(f"chunk_size is {chunk_size_mib} MiB for file size {file_size_mib} bytes"
                     f"(etag parts: {etag_parts})")
        with open(file_path, 'rb') as fh:
            for data in iter(lambda: fh.read(chunk_size), b''):
                md5s.append(hashlib.md5(data).digest())
        digests_md5 = hashlib.md5(b''.join(md5s))
        etag_checksum = f'{digests_md5.hexdigest()}-{etag_parts}'
        logger.debug(f'calculated etag: {etag_checksum}')
        return etag_checksum

    def etag_compare(self, file_path, etag_source, file_size):
        '''https://stackoverflow.com/a/58239738'''
        etag_source = etag_source.strip('"')
        etag_local = ''
        if '-' in etag_source:
            etag_parts = int(re.search(r'^.+-([0-9]+$)', etag_source).group(1))
            etag_local = self.etag_checksum(file_path, etag_parts=etag_parts, file_size=file_size)
        elif '-' not in etag_source:
            etag_local = self.md5_checksum(file_path)
        if etag_source == etag_local:
            return True
        else:
            logger.warning(f'    source etag checksum: {etag_source}')
            logger.warning(f'     local etag checksum: {etag_local}')
        return False
