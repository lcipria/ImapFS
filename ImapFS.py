import config
import os
import sys
import imaplib
import email
import time
import re
from fuse import FUSE, FuseOSError, Operations

class ImapFS(Operations):
    def __init__(self):
        self.client = imaplib.IMAP4_SSL(config.mail_server)
        resp_code, response = self.client.login(config.mail_username, config.mail_password)

    def getattr(self, path, fh=None):
        print(f'getattr({path}, {fh}')
        if self.__path_is_folder__(path):
            return {
                'st_atime': 0,
                'st_ctime': 0,
                'st_mtime': 0,
                'st_mode': 0o40555,
                'st_nlink': 2,
                'st_size': 4096,
                'st_uid': 0,
                'st_gid': 0,
                }
        else:
            return {
                'st_atime': 0,
                'st_ctime': 0,
                'st_mtime': 0,
                'st_mode': 0o100444,
                'st_nlink': 1,
                'st_size': 4096, # correggere
                'st_uid': 0,
                'st_gid': 0,
                }

    def readdir(self, path, fh):
        print(f'readdir({path}, {fh})')
        if self.__path_is_folder__(path):
            normpath = os.path.normpath(f'{config.mail_folder}/{path}')
            base_depth = normpath.count('/') + 1
            for entry in self.client.list(normpath)[1]:
                if entry:
                    for folder in re.findall('(?<="/" ").+(?="$)', entry.decode()):
                        split = os.path.normpath(folder).split('/')
                        if len(split) == base_depth + 1:
                            yield('/'.join(split[base_depth:base_depth+1]))
            yield('.')
            yield('..')

    def read(self, path, size, offset, fh):
        print(f'read({path}, {size}, {offset}, {fh})')
        if self.__path_is_file__(path):
            resp_code, response = self.client.fetch('1', '(RFC822)')
            if resp_code.lower() == 'ok':
                block = email.message_from_string(response[0][1].decode())
                return block.get_payload().encode('utf-8')#[offset:offset + size]

    def write(self, path, data, offset, fh):
        print(f'write({path}, data, {offset}, {fh})')
        if self.__path_exists__(path):
            self.client.delete(os.path.normpath(f'{config.mail_folder}/{path}'))
        self.client.create(os.path.normpath(f'{config.mail_folder}/{path}'))
        self.__create_block__(path, data)
        return len(data)

    def __check_path__(self, path):
        return self.client.select(os.path.normpath(f'{config.mail_folder}/{path}'))

    def __path_exists__(self, path):
        resp_code, response = self.__check_path__(path)
        return resp_code.lower() == 'ok'

    def __path_is_folder__(self, path):
        resp_code, response = self.__check_path__(path)
        if resp_code.lower() == 'ok':
            return int(response[0]) == 0

    def __path_is_file__(self, path):
        resp_code, response = self.__check_path__(path)
        if resp_code.lower() == 'ok':
            return int(response[0])

    def __create_block__(self, path, data):
        block = email.message.Message()
        block.set_payload(data)
        self.client.append(
            os.path.normpath(f'{config.mail_folder}/{path}'),
            '',
            imaplib.Time2Internaldate(time.time()),
            str(block).encode("utf-8"))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"uso: {sys.argv[0]} <mountpoint>")
        sys.exit(1)

    fuse = FUSE(ImapFS(), sys.argv[1], foreground=True)
