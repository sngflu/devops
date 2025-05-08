from minio_storage import MinioStorage

storage = MinioStorage(external_endpoint='192.168.0.102:9000')
storage.connect()

filename = storage.list_user_videos('aleks')[0]['filename']

print(filename)


print(storage.get_presigned_url(filename))