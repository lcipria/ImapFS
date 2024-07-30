from email import message, message_from_string
from fuse import FUSE, FuseOSError, Operations
import config
import errno
import imaplib
import os
import re
import sys
import time

class ImapFS(Operations):
    def __init__(self):
        self.client = imaplib.IMAP4_SSL(config.mail_server)
        resp_code, response = self.client.login(config.mail_username, config.mail_password)

    def getattr(self, path, fh=None):
        print(f'getattr({path}, {fh})')
        if self.__path_is_folder__(path):
            return {
                'st_atime': 0,
                'st_ctime': 0,
                'st_mtime': 0,
                'st_mode': 0o40777,
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
                'st_mode': 0o100666,
                'st_nlink': 1,
                'st_size': 4096, # correggere
                'st_uid': 0,
                'st_gid': 0,
                }

    def readdir(self, path, fh):
        print(f'readdir({path}, {fh})')
        if self.__path_is_folder__(path):
            normpath = self.__normpath__(path)
            base_depth = normpath.count('/')
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
                block = message_from_string(response[0][1].decode())
                return block.get_payload().encode('utf-8')[offset:offset + size]

    def write(self, path, data, offset, fh):
        print(f'write({path}, data, {offset}, {fh})')
        if self.__path_exists__(path):
            self.client.delete(self.__normpath__(path))
        self.client.create(self.__normpath__(path))

        block = message.Message()
        block.set_payload(data)
        self.client.append(
            self.__normpath__(path),
            '',
            imaplib.Time2Internaldate(time.time()),
            str(block).encode("utf-8"))

        return len(data)

    def access(self, path, mode):
        print(f'access({path}, {mode})')

    def chmod(self, path, mode):
        print(f'chmod({path}, {mode})')

    def chown(self, path, uid, gid):
        print(f'chown({path}, {uid}, {gid})')

    def create(self, path, mode, fi=None):
        print(f'create({path}, {mode}, {fi})')

    def flush(self, path, fh):
        print(f'flush({path}, {fh})')

    def fsync(self, path, fdatasync, fh):
        print(f'fsync({path}, {fdatasync}, {fh})')

    def link(self, target, name):
        print(f'link({target}, {name})')

    def mkdir(self, path, mode):
        print(f'mkdir({path}, {mode})')
        if not self.__path_exists__(path):
            self.client.create(self.__normpath__(path))

    def mknod(self, path, mode, dev):
        print(f'mknod({path}, {mode}, {dev})')

    def open(self, path, flags):
        print(f'open({path}, {flags})')
        accmode = flags & os.O_ACCMODE
        if accmode == os.O_RDONLY:
            if self.__path_is_file__(path):
                return 0
            else:
                return -errno.ENOENT
        elif accmode == os.O_WRONLY:
            if flags & os.O_APPEND:
                print("append")
            if self.__path_is_file__(path):
                return 0
            else:
                return -errno.ENOENT

        elif accmode == os.O_RDWR:
            if flags & os.O_APPEND:
                print("append")
            return 0
        else:
            return -errno.EACCES

    def readlink(self, path):
        print(f'readlink({path})')

    def release(self, path, fh):
        print(f'release({path}, {fh})')

    def rename(self, old, new):
        print(f'rename({old}, {new})')

    def rmdir(self, path):
        print(f'rmdir({path})')
        if self.__path_is_folder__(path):
            self.client.delete(self.__normpath__(path))

    def statfs(self, path):
        print(f'statfs({path})')

    def symlink(self, name, target):
        print(f'symlink({name}, {target})')

    def truncate(self, path, length, fh=None):
        print(f'truncate({path}, {length}, {fh})')

    def unlink(self, path):
        print(f'unlink({path})')
        if self.__path_is_file__(path):
            self.client.delete(self.__normpath__(path))

    def utimens(self, path, times=None):
        print(f'utimens({path}, {times})')

    def __check_path__(self, path):
        normpath = self.__normpath__(path)
        return self.client.select(normpath)

    def __path_exists__(self, path):
        resp_code, response = self.__check_path__(path)
        return resp_code.lower() == 'ok'

    def __path_is_folder__(self, path):
        resp_code, response = self.__check_path__(path)
        if resp_code.lower() == 'ok':
            return int(response[0]) == 0
        return False

    def __path_is_file__(self, path):
        resp_code, response = self.__check_path__(path)
        if resp_code.lower() == 'ok':
            return int(response[0])
        return False

    def __normpath__(self, path):
        return os.path.normpath(f'"{config.mail_folder}/{path}"')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"uso: {sys.argv[0]} <mountpoint>")
        sys.exit(1)

    fuse = FUSE(ImapFS(), sys.argv[1], foreground=True)
