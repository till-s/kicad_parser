#!/usr/bin/env python3
import sys
import getopt
from kicad_sch import *
import re

if __name__ == "__main__":
  opts, args = getopt.getopt(sys.argv[1:], "hm:b:rp")
  basPrjName = None
  subShtName = None
  reannotate = False
  
  for o,a in opts:
    if o == '-h':
      print("Reannotate sub-project in top-project to match references in sub-project as stand-alone")
      print("  -h           : this message.")
      print("  -b           : top project name (*not* schematics name; i.e., basename of schematics file).")
      print("                 Schematics is assumed to be '<top-project-name>.kicad_sch'")
      print("  -m           : sub *sheet* name (*not* schematics nor project name; i.e., basename of schematics file).")
      print("                 Multiple instances of the same sub-project sheet may be present in  the super-project")
      print("                 but each of these must have a unique sheet name.")
      print("  -p           : just print sub-project UUID (to be passed as merge_pcb.py -p <uuid>).")
      print("                 Note that this is the default; i.e., UUID is shown w/o explicit '-p'.")
      print("  -r           : reannotate top-project: REWRITES ALL SCHEMATICS FILES!!")
      sys.exit(0)
    elif o == '-p':
      pass
    elif o == '-r':
      reannotate = True
    elif o == '-b':
      basPrjName = a
    elif o == '-m':
      subShtName = a
  if ( basPrjName is None ):
    raise RuntimeError("Top-project missing; must use -b <top-project-name> option")
  if ( subShtName is None ):
    raise RuntimeError("Sub-sheet name missing; must use -m <sub-sheet-name> option")
  print("Sub-project UUID (use with merge_pcb.py -p <uuid>): {}".format( KicadSch.getMergePcbPrefix(basPrjName, subShtName) ))
  if reannotate:
    KicadSch.reannotate(basPrjName, subShtName)
