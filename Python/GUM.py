# GUM - Python
# Adapted from Hoikas' and branan's scripts:
# https://github.com/branan/moulbuild-scripts

from __future__ import print_function
from hashlib import md5
from optparse import OptionParser # argparse sucks.
from PyHSPlasma import *
import gzip
import os, os.path
import tempfile
import shutil

# Preparing.
done = {}
class ProcessedFile:
    hash_un = None
    hash_gz = None
    size_un = 0
    size_gz = 0

# Constants.
kNone             = 0x00
kDualChannelOgg   = 0x01
kStreamOgg        = 0x02
kStereoOgg        = 0x04

# Temporary directory.
tmpdir = tempfile.mkdtemp()

# Parser options.
parser = OptionParser()
parser.add_option("-d", "--droid", dest="droid",
   help="DROID key to use for SecurePreloader lists", metavar="DROID",
   default="31415926535897932384626433832795")
parser.add_option("-s", "--source", dest="source",
   help="Reference install to use as a SOURCE", metavar="SOURCE",
   default="C:\\Program Files\\Uru Live")
(options, args) = parser.parse_args()

# Function definitions.
def create_manifest(name):
    if not os.path.exists("FileSrv"):
        os.mkdir("FileSrv")
    
    file = open(os.path.join("FileSrv", name + ".mfs"), "w+")
    return file


def do_file(file, src, subfolder = None, flag = kNone, encrypt=False):
    global done
    
    if subfolder:
        gzpath = os.path.join(subfolder, file + ".gz")
    else:
        gzpath = file + ".gz"
    
    if file in done:
        f = done[file]
    else:
        realpath = os.path.join(src, file)
        if subfolder:
            endpath = os.path.join("FileSrv", os.path.join(subfolder, file + ".gz"))
        else:
            endpath = os.path.join("FileSrv", file + ".gz")
        
        tomake = os.path.split(endpath)[0]
        if not os.path.exists(tomake):
            os.makedirs(tomake)
        
        if not os.path.isfile(realpath):
            plDebug.Error("WARNING: Can't find: %s" % realpath)
            return ""

        if encrypt:
            fname = os.path.basename(file)
            tmppath = os.path.join(tmpdir, fname)
            handle = open(realpath, "rb")
            data = handle.read()
            handle.close()
            stream = plEncryptedStream()
            stream.open(tmppath, fmCreate, plEncryptedStream.kEncXtea)
            stream.write(data)
            stream.close()
            readpath = tmppath
        else:
            readpath = realpath
            
        
        f = ProcessedFile()
        handle = open(readpath, "rb")
        content = handle.read()
        f.hash_un = md5(content).hexdigest()
        handle.close()
        
        gz = gzip.open(endpath, mode='w+b')
        gz.write(content)
        gz.close()
        
        handle = open(endpath, "rb")
        f.hash_gz = md5(handle.read()).hexdigest()
        handle.close()

        stat    = os.stat(readpath)
        stat_gz = os.stat(endpath)

        if encrypt:
            os.unlink(tmppath)

        f.size_un = stat.st_size
        f.size_gz = stat_gz.st_size
        done[file] = f
    
    line = "%s,%s,%s,%s,%s,%s,%s" % (file.replace("/", "\\"), gzpath, f.hash_un, f.hash_gz, f.size_un, f.size_gz, flag)
    print(line)
    return line + "\n"


def make_age_mfs(age, src):    
    mfs = create_manifest(age)
    mfs.write(do_file(os.path.join("dat", age + ".age"), src, encrypt=True))
    
    fni = os.path.join("dat", age + ".fni")
    if os.path.exists(os.path.join(src, fni)):
        mfs.write(do_file(fni, src, encrypt=True))
    csv = os.path.join("dat", age + ".csv")
    if os.path.exists(os.path.join(src, csv)):
        mfs.write(do_file(csv, src, encrypt=False))
    
    res = plResManager()
    agepath = os.path.join(os.path.join(src, "dat"), age + ".age")
    info = res.ReadAge(agepath, True)
    ver = res.getVer()
    
    for i in range(info.getNumCommonPages(ver)):
        prp = info.getCommonPageFilename(i, ver)
        mfs.write(do_file(os.path.join("dat", prp), src))
    
    for i in range(info.getNumPages()):
        prp = info.getPageFilename(i, ver)
        mfs.write(do_file(os.path.join("dat", prp), src))
    
    for loc in res.getLocations():
        for key in res.getKeys(loc, plFactory.ClassIndex("plSoundBuffer")):
            sbuf = key.object
            
            flags = kNone
            if (sbuf.flags & plSoundBuffer.kOnlyLeftChannel) or (sbuf.flags & plSoundBuffer.kOnlyRightChannel):
                flags |= kDualChannelOgg
            else:
                flags |= kStereoOgg
            
            if sbuf.flags & plSoundBuffer.kStreamCompressed:
                flags |= kStreamOgg
            
            mfs.write(do_file(os.path.join("sfx", sbuf.fileName), src, flag=flags))
    
    del res
 
 
def make_all_age_mfs(src):
    dir = os.listdir(os.path.join(src, "dat"))
    for entry in dir:
        if entry[len(entry) - 4:].lower() != ".age":
            continue
        
        make_age_mfs(entry[:len(entry) - 4], src)   


def make_client_mfs(src):
    internal = create_manifest("Internal")
    external = create_manifest("External")
    dir = os.listdir(src)
    
    gotExt = False
    gotInt = False
    for entry in dir:
        path = os.path.join(src, entry)
        
        if not os.path.isfile(path):
            continue
        if entry[len(entry) - 4:].lower() == ".lnk":
            continue
        if entry.lower() == "urulauncher.exe" or entry.lower() == "plurulauncher.exe":
            continue
        if entry[len(entry) - 4:].lower() == ".ini":
            continue
        
        line = do_file(entry, src, "Client")
        
        if entry.lower() == "plclient.exe":
            internal.write(line)
            gotInt = True
        elif entry.lower() == "uruexplorer.exe":
            external.write(line)
            gotExt = True
        elif entry.lower() == "plcrashhandler.exe":
            internal.write(line)
        elif entry.lower() == "urucrashhandler.exe":
            external.write(line)
        else:
            internal.write(line)
            external.write(line)
    
    avi = os.path.join(src, "avi")
    dir = os.listdir(avi)
    for entry in dir:
        path = os.path.join(avi, entry)
        rel = os.path.relpath(path, src)
        ext = entry[len(entry) - 4:].lower()
        
        if not os.path.isfile(path):
            continue
        if not (ext == ".avi" or ext == ".bik" or ext == ".ogg" or ext == ".ogv"):
            continue
        
        line = do_file(rel, src)
        internal.write(line)
        external.write(line)

    avi = os.path.join(src, "dat")
    dir = os.listdir(avi)
    for entry in dir:
        path = os.path.join(avi, entry)
        rel = os.path.relpath(path, src)
        ext = entry[len(entry) - 4:].lower()
        
        if not os.path.isfile(path):
            continue
        if ext == ".age":
            line = do_file(rel, src, encrypt=True)
        elif ext == ".p2f"  or ext == ".loc":
            line = do_file(rel, src)
        else:
            continue
        
        internal.write(line)
        external.write(line)
    
    internal.close()
    external.close()
    
    if not gotExt:
        os.unlink(os.path.join("FileSrv", "External.mfs"))
    if not gotInt:
        os.unlink(os.path.join("FileSrv", "Internal.mfs"))
   
    if gotExt:
        shutil.copy(os.path.join("FileSrv", "External.mfs"), os.path.join("FileSrv", "ThinExternal.mfs"))
    if gotInt:
        shutil.copy(os.path.join("FileSrv", "Internal.mfs"), os.path.join("FileSrv", "ThinInternal.mfs"))


def make_new_preloader_mfs(src, key):
    def buf_to_int(str):
        val = 0
        val += (int(str[0], 16) * 0x10000000) + (int(str[1], 16) * 0x01000000)
        val += (int(str[2], 16) * 0x00100000) + (int(str[3], 16) * 0x00010000)
        val += (int(str[4], 16) * 0x00001000) + (int(str[5], 16) * 0x00000100)
        val += (int(str[6], 16) * 0x00000010) + (int(str[7], 16) * 0x00000001)
        return val
    
    def do_auth_file(path):
        rel = os.path.relpath(path, src)
        tmpfile = os.path.join(tmpdir, rel)
        handle = open(path, "rb")
        data = handle.read()
        handle.close()
        stream = plEncryptedStream()
        stream.open(tmpfile, fmCreate, plEncryptedStream.kEncDroid)
        stream.setKey(droid)
        stream.write(data)
        stream.close()
        line = do_file(rel, tmpdir)
        preloader.write(line)
        os.unlink(tmpfile)
    
    droid = []
    droid.append(buf_to_int(key[0:8]))
    droid.append(buf_to_int(key[8:16]))
    droid.append(buf_to_int(key[16:24]))
    droid.append(buf_to_int(key[24:32]))
    
    preloader = create_manifest("SecurePreloader")
    pydir = os.path.join(src, "Python")
    sdldir = os.path.join(src, "SDL")
    os.mkdir(os.path.join(tmpdir, "Python"))
    os.mkdir(os.path.join(tmpdir, "SDL"))
    dir = os.listdir(pydir)
    for entry in dir:
        path = os.path.join(pydir, entry)
        ext = os.path.splitext(path)[1]
        if not os.path.isfile(path):
            continue
        if ext != ".pak":
            continue
        do_auth_file(path)
    
    dir = os.listdir(sdldir)
    for entry in dir:
        path = os.path.join(sdldir, entry)
        ext = os.path.splitext(path)[1]
        if not os.path.isfile(path):
            continue
        if ext != ".sdl":
            continue
        do_auth_file(path)
    preloader.close()
    os.rmdir(os.path.join(tmpdir, "Python"))
    os.rmdir(os.path.join(tmpdir, "SDL"))

def make_patcher_mfs(src):
    il = os.path.join(src, "plUruLauncher.exe")
    el = os.path.join(src, "UruExplorer.exe")
    si = do_file("server.ini", src, "Patcher")
    
    if os.path.isfile(il):
        internal = create_manifest("InternalPatcher")
        internal.write(do_file("plUruLauncher.exe", src, "Patcher"))
        internal.write(si)
        internal.close()
    
    if os.path.isfile(el):
        external = create_manifest("ExternalPatcher")
        external.write(do_file("UruLauncher.exe", src, "Patcher"))
        external.write(si)
        external.close()
        
# Begin execution.
make_patcher_mfs(options.source)
make_client_mfs(options.source)
make_new_preloader_mfs(options.source, options.droid)
make_all_age_mfs(options.source)
os.rmdir(tmpdir)

blacklist = open("blacklist.txt")
for line in blacklist:
    os.unlink("FileSrv/"+line.strip()+".gz")
