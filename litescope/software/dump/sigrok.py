import os
import math
import shutil
import zipfile
import re
from collections import OrderedDict

from litescope.software.dump.common import Dump, DumpVariable


class SigrokDump(Dump):
    def __init__(self, dump=None, samplerate=None):
        Dump.__init__(self)
        self.variables = [] if dump is None else dump.variables
        self.samplerate = 100e6 if samplerate is None else samplerate

    def write_version(self):
        f = open("version", "w")
        f.write("1")
        f.close()

    def write_metadata(self, name):
        f = open("metadata", "w")
        r = """
[global]
sigrok version = 0.2.0
[device 1]
driver = litescope
capturefile = dump
unitsize = 1
total probes = {}
samplerate = {} KHz
""".format(
        len(self.variables),
        self.samplerate//1000*2,
    )
        for i, variable in enumerate(self.variables):
            r += "probe{} = {}\n".format(i + 1, variable.name)
        f.write(r)
        f.close()

    def write_data(self):
        # TODO: study bytes/bits ordering to remove limitation
        assert len(self.variables) < 8 
        data_bits = math.ceil(len(self.variables)/8)*8
        data_len = 0
        for variable in self.variables:
            data_len = max(data_len, len(variable))
        datas = []
        for i in range(data_len):
            data = 0
            for j, variable in enumerate(reversed(self.variables)):
                data = data << 1
                try:
                    data |= variable.values[i] & 0x1 # 1 bit probes
                except:
                    pass
            datas.append(data)
        f = open("dump", "wb")
        for data in datas:
            f.write(data.to_bytes(data_bits//8, "big"))
        f.close()

    def zip(self, name):
        f = zipfile.ZipFile(name + ".sr", "w")
        os.chdir(name)
        f.write("version")
        f.write("metadata")
        f.write("dump")
        os.chdir("..")
        f.close()

    def write(self, filename):
        name, ext = os.path.splitext(filename)
        if os.path.exists(name):
            shutil.rmtree(name)
        os.makedirs(name)
        os.chdir(name)
        self.write_version()
        self.write_metadata(name)
        self.write_data()
        os.chdir("..")
        self.zip(name)
        shutil.rmtree(name)

    def unzip(self, filename, name):
        f = open(filename, "rb")
        z = zipfile.ZipFile(f)
        if os.path.exists(name):
            shutil.rmtree(name)
            os.makedirs(name)
        for file in z.namelist():
            z.extract(file, name)
        f.close()

    def read_metadata(self):
        probes = OrderedDict()
        f = open("metadata", "r")
        for l in f:
            m = re.search("probe([0-9]+) = (\w+)", l, re.I)
            if m is not None:
                index = int(m.group(1))
                name = m.group(2)
                probes[name] = index
            m = re.search("samplerate = ([0-9]+) kHz", l, re.I)
            if m is not None:
                self.samplerate = int(m.group(1))*1000
            m = re.search("samplerate = ([0-9]+) mHz", l, re.I)
            if m is not None:
                self.samplerate = int(m.group(1))*1000000
        f.close()
        return probes

    def read_data(self, name, nprobes):
        datas = []
        f = open("dump", "rb")
        while True:
            data = f.read(math.ceil(nprobes/8))
            if data == bytes('', "utf-8"):
                break
            data = int.from_bytes(data, "big")
            datas.append(data)
        f.close()
        return datas

    def read(self, filename):
        self.variables = []
        name, ext = os.path.splitext(filename)
        self.unzip(filename, name)
        os.chdir(name)
        probes = self.read_metadata()
        datas = self.read_data(name, len(probes.keys()))
        os.chdir("..")
        shutil.rmtree(name)

        for k, v in probes.items():
            probe_data = []
            for data in datas:
                probe_data.append((data >> (v-1)) & 0x1)
            self.add(DumpVariable(k, 1, probe_data))
