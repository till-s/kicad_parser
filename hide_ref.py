#!/usr/bin/env python3
from kicad_pcb import *
import getopt
import sys

# for debugging find a footprint with a specified reference designator
def fndref(nam):
  for fp in pcb['footprint']:
    for txt in fp['fp_text']:
      if ( txt[0] == 'reference' and txt[1] == '"{}"'.format(nam) ):
        return fp,txt

# hide *all* reference designators
def hide_all_refs(pcb):
  for fp in pcb['footprint']:
    for txt in fp['fp_text']:
      if ( txt[0] == 'reference' ):
         # action 0 replaces existing value
         txt._value.add(SexpDefaultTrue('hide',True), 0)

if ( __name__ == "__main__" ):
  outf = None
  inpf = None
  if ( len(sys.argv) < 2 ):
    opts=[('-h',None)]
  else:
    opts, args = getopt.getopt(sys.argv[1:],"hf:o:")
  for o,a in opts:
    if ( o == '-h' ):
      print("usage: {} [-h] -f <pcb-input-file> [-o <pcb-output-file]".format(sys.argv[0]))
      print("Hide all reference designators of a PCB")
      print("    -h        : this message.")
      print("    -f        : file to process")
      print("    -o        : where to write output (stdout by default)")
      sys.exit(0)
    elif( o == '-f' ):
      print("-f has {}".format(a))
      inpf = a
    elif( o == '-o' ):
      outf = a

  if ( inpf is None ):
    raise RuntimeError("Missing -f <pcb_file> argument")

  pcb = KicadPCB.load(inpf)

  hide_all_refs(pcb)

  if ( outf is None ):
    pcb.export( sys.stdout )    
  else:
    with open(outf,'w') as f:
      pcb.export(f)
