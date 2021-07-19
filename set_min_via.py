#!/usr/bin/env python3

from kicad_pcb import *
from sexp_parser import *
import sys
import getopt
import re
import io

mind   = None
pcbf   = None

opts, args = getopt.getopt(sys.argv[1:], "hd:f:")
for o, a in opts:
  if o == '-h':
    print("set via parameters"       , file=sys.stderr)
    print(" -d <dia> : min diameter" , file=sys.stderr)
    print(" -f <file>: input file"   , file=sys.stderr)
  elif o == '-d': 
    mind = float(a)
  elif o == '-f':
    pcbf = a
  else:
    raise RuntimeError("Unknown option: " + o)

if pcbf is None:
  raise RuntimeError("Missing file (use -f option)")

if mind is None:
  print("Nothing to do -- missing option?", file=sys.stderr)


pcb = KicadPCB.load(pcbf)
for v in pcb['via']:
  if v['size'] < mind:
    v._value.add(Sexp('size',mind),0)
pcb.export(sys.stdout)
