# -*- coding: utf-8 -*-
# Based on code by pgid69 on OpenWRT forums:
#  https://forum.openwrt.org/viewtopic.php?pid=183315#p183315
#
# Allows to write on u-boot memory on modems not supporting 'loadb' commands
#  python uboot-write.py --write=open-wrt-image.bin --addr=0x81000000
#
# Once memory is written, go with the classic way (use proper addresses for your device):
#  erase 0x9f020000 +0x3c0000
#  cp.b 0x81000000 0x9f020000 0x3c0000
#  bootm 9f020000
#

from __future__ import division #1/2 = float, 1//2 = integer, python 3.0 behaviour in 2.6, to make future port to 3 easier.
from __future__ import print_function
from optparse import OptionParser
import os
import struct
import sys
import zlib

debug = False
if not debug:
        import serial

# The maximum size to transfer if we can determinate the size of the file (if input data comes from stdin).
MAX_SIZE = 2 ** 30
LINE_FEED = "\n"

# Wait for the prompt
def getprompt(ser, addr, verbose):

        # Send a command who does not produce a result so when receiving the next line feed, only show the prompt will be returned
        ser.write("mw {0:08x} 0".format(addr) + LINE_FEED)
        # Flushing read buffer
        while ser.read(256):
                pass
        if verbose:
                print("Waiting for a prompt...", file = sys.stderr)
        while True:
                # Write carriage return and wait for a response
                ser.write(LINE_FEED)
                # Read the response
                buf = ser.read(256);
                if (buf.endswith(b"> ")):
                        if verbose:
                                print("Ok, prompt is '", buf, "'", sep='', file = sys.stderr)
                        # The prompt returned starts with a line feed. This is the echo of the line feed we send to get the prompt.
                        # We keep this linefeed
                        return buf
                else:
                        # Flush read buffer
                        while ser.read(256):
                                pass

# Wait for the prompt and return True if received or False otherwise
def writecommand(ser, command, prompt, verbose):

        # Write the command and a line feed, so we must get back the command and the prompt
        ser.write(command)
        ser.write(LINE_FEED)

        buf = ser.read(len(command))
        if (buf != command):
                if verbose:
                        print("Echo command not received. Instead received '", buf, "'", sep='', file = sys.stderr)
                return False

        if verbose:
                print("Waiting for prompt...", file = sys.stderr)

        buf = ser.read(len(prompt))
        if (buf == prompt):
                if verbose:
                        print("Ok, prompt received", file = sys.stderr)
                return True
        else:
                if verbose:
                        print("Prompt not received. Instead received '", buf, "'", sep='', file = sys.stderr)
                return False

def memwrite(ser, path, size, start_addr, verbose, debug):

        if not debug:
                prompt = getprompt(ser, start_addr, verbose)

        if (path == "-"):
                fd = sys.stdin
                if (size <= 0):
                        size = MAX_SIZE
        else:
                fd = open(path,"rb")
                if (size <= 0):
                        # Get the size of the file
                        fd.seek(0, os.SEEK_END);
                        size = fd.tell();
                        fd.seek(0, os.SEEK_SET);

        addr = start_addr
        bytes_read = 0
        crc32_checksum = 0
        while (bytes_read < size):
                if ((size - bytes_read) > 4):
                        read_bytes = fd.read(4);
                else:
                        read_bytes = fd.read(size - bytes_read);

                if (len(read_bytes) == 0):
                        if (path == "-"):
                                size = bytes_read
                        break

                bytes_read += len(read_bytes)
                crc32_checksum = zlib.crc32(read_bytes, crc32_checksum) & 0xFFFFFFFF

                while (len(read_bytes) < 4):
                        read_bytes += b'\x00'

                (val, ) = struct.unpack(">L", read_bytes)
                read_bytes = "".format(val)

                str_to_write = "mw {0:08x} {1:08x}".format(addr, val)
                if verbose:
                        print("Writing:", str_to_write, "at:", "0x{0:08x}".format(addr), file = sys.stderr)

                if debug:
                        str_to_write = struct.pack(">L", int("{0:08x}".format(val), 16))

                if not debug:
                        if not writecommand(ser, str_to_write, prompt, verbose):
                                print("Found an error, so aborting", file = sys.stderr)
                                return

                # Increment address
                addr += 4

        if (bytes_read != size):
                print("Error while reading file '", fd.name, "' at offset ", bytes_read, sep='', file = sys.stderr)
        else:
                print("File successfully written. You should run command 'crc32", " {0:08x}".format(start_addr), " {0:08x}".format(bytes_read), "' on the modem and the result must be", " {0:08x}".format(crc32_checksum), ".", sep='', file = sys.stderr)

        fd.close()
        return

def main():

        optparser = OptionParser("usage: %prog [options]", version = "%prog 0.1")
        optparser.add_option("--verbose", action = "store_true", dest = "verbose", help = "be verbose", default = False)
        optparser.add_option("--serial", dest = "serial", help = "specify serial port", default = "/dev/ttyUSB0", metavar = "dev")
        optparser.add_option("--write", dest = "write", help = "write mem from file", metavar = "path")
        optparser.add_option("--addr", dest = "addr", help = "mem address", default = "0x81000000", metavar = "addr")
        optparser.add_option("--size", dest = "size", help = "# bytes to write", default = "0", metavar = "size")
        (options, args) = optparser.parse_args()
        if (len(args) != 0):
                optparser.error("incorrect number of arguments")

        if not debug:
                ser = serial.Serial(options.serial, 115200, timeout=1)
        else:
                ser = open(options.write + ".out", "wb")

        if debug:
                prompt = getprompt(ser, options.verbose)
                writecommand(ser, "mw 80500000 01234567", prompt, options.verbose)
                buf = ser.read(256)
                print("buf = '", buf, "'", sep = "")
                return

        if options.write:
                memwrite(ser, options.write, int(options.size, 0), int(options.addr, 0), options.verbose, debug)
        return

if __name__ == '__main__':
        main()