#!/usr/bin/env python3

from kicad_pcb import *
from sexp_parser import *
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("filename",nargs='?')
parser.add_argument("-l", "--log", dest="logLevel", 
    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], 
    help="Set the logging level")
parser.add_argument("-o", "--output", help="output filename")
args = parser.parse_args()    
logging.basicConfig(level=args.logLevel,
        format="%(filename)s:%(lineno)s: %(levelname)s - %(message)s")

fnam = '../trigbox/test-boards/power-test-module/power-test-module.kicad_pcb' if args.filename is None else args.filename

class RefRecord(object):
  def __init__(self, module):
    self._s = list()
    self._m = module
    self.record(self.getModule().getPcb())

  def has(self, o):
    if isinstance(o, Sexp):
      o = o._value
    return o in self._s

  def record(self, o):
    if isinstance(o, Sexp):
      o = o._value
    if self.has(o):
      raise RuntimeError("RefAction: object already in set")
    self._s.append(o)

  def getModule(self):
    return self._m

class RefCheck(object):
  def __init__(self, refs):
    self._refs = refs
    self._errs = 0
    refs.getModule().visit(self)
    if self._errs != 0:
      raise RuntimeError("Reference checking failed")

  def __call__(self, o, path):
    for key in ['net', 'net_name']:
      try:
        o[key]
        if not self._refs.has(o):
          print("{} ({}) has '{}' but no ref found".format('.'.join(path), o, key))
          self._errs = self._errs + 1
      except KeyError:
        pass
      except TypeError:
        pass

class RefVerify(RefRecord):
  def __init__(self, module):
    RefRecord.__init__(self, module)
    module.visitNetlist(self)
    module.visitZones(self)
    module.visitSegments(self)
    module.visitPads(self)
    module.visitVias(self)
    module.visit(RefCheck(self))

  def __call__(self, o):
    self.record(o)

class NetRemap(RefRecord):
  def __init__(self, module, netMap):
    RefRecord.__init__(self, module)
    self._map = netMap

  def remap(self, net):
    return self._map[net]

class FixupMap(object):
  def __init__(self, remap):
    self._remp = remap

  def __call__(self, o):
    o['net'] = self._remp.remap(o['net'])
    self._remp.record( o )

class FixupNetList(object):
  def __init__(self, remap):
    self._remp = remap

  def __call__(self, o):
    o._value[0] = self._remp.remap(o._value[0])
    self._remp.record( o )

class FixupPad(object):
  def __init__(self, remap):
    self._remp = remap

  def __call__(self, o):
    o['net'][0] = self._remp.remap(o['net'][0])
    self._remp.record( o )

class PCBPart(object):

  def __init__(self, fnam):
    pcb = KicadPCB.load(fnam)
    # check for error
    haveErrs = False
    for e in pcb.getError():
      print('Error: {}'.format(e))
      haveErrs = True
    if haveErrs:
      raise RuntimeError("Parsing Errors Encoutered")
    self._pcb   = pcb
    self._nl    = pcb['net']
    self._nm    = dict()
    self._vdbg  = False
    # check if it is consecutive
    i         = 0
    for e in self._nl:
      if e[0] != i:
        raise RuntimeError("non-consecutive netlist")
      try:
        if self._nm[e[1]]:
          raise RuntimeError("duplicate net-name?")
      except KeyError:
        pass
      self._nm[e[1]] = e
      i = i + 1

  def getNetNames(self):
    return self._nm

  def getPcb(self):
    return self._pcb

  def visitNetlist(self, action=None):
    for e in self._nl:
      if action is None:
        print("[{:d}] -> {}".format(e[0], e[1]))
      else:
        action(e)

  def visitZones(self, action=None):
    for z in self._pcb['zone']:
      # consistency check
      netnam = z['net_name']
      try:
        self._nm[netnam]
      except KeyError:
        raise RuntimeError("zone net name not found in net-name list??")
      if action is None:
        print("net [{:d}] -- {}".format(z['net'], z['net_name']))
      else:
        action(z)

  def visitSegments(self, action=None):
    for s in self._pcb['segment']:
      if action is None:
        print("net [{:d}]".format(s['net']))
      else:
        action(s)

  def visitVias(self, action=None):
    for v in self._pcb['via']:
      if action is None:
        print("via [{:d}]".format(v['net']))
      else:
        action(v)

  def visitPads(self, action=None):
    for m in self._pcb['module']:
      for p in m['pad']:
        try:
          n = p['net']
          try:
            self._nm[n[1]]
          except KeyError:
            raise RuntimeError("pad net name not found in net-name list??")
          if not action is None:
            action(p)
        except KeyError:
          n = (-1, "<unconnected>")
        if action is None:
          print("net [{:d}] -- {}".format(n[0], n[1]))

  def visit(self, action, o = None, path=[]):
    if o is None:
      o = self._pcb
    action(o, path)
    if ( isinstance(o, SexpValueDict) ):
      if self._vdbg:
        print('(DICT')
      for k in o:
        if self._vdbg:
          print('  k: {}'.format(k))
        path.append(str(k))
        self.visit(action, o[k], path)
        path.pop()
    elif ( isinstance(o, SexpList) ):
      if self._vdbg:
        print('(SLIST k: {}'.format(o._key))
      #path.append(str(o._key))
      idx = 0
      for e in o._value:
        path.append("[{:d}]".format(idx))
        if self._vdbg:
          print("slistel: {}".format(type(e)))
        self.visit(action, e, path)
        idx = idx + 1
        path.pop()
      #path.pop()
    elif ( isinstance(o, Sexp) ):
      if self._vdbg:
        print("(BASE k: {}'".format(o._key))
      #path.append(str(o._key))
      self.visit(action, o._value, path)
      #path.pop()
    elif ( isinstance(o, list) ):
      if self._vdbg:
        print("(list")
      for e in o:
        self.visit(action, e, path)
    else:
      if self._vdbg:
        print("( plain ({}): {}".format(type(o),o))
    if self._vdbg:
      print(')')

  def export(self, out, indent='  '):
    self._pcb.export(out, indent)

  def fixupNets(self, netMap):
    refs   = NetRemap(self, netMap)
    fixMap = FixupMap(refs)
    self.visitNetlist(FixupNetList(refs))
    self.visitZones(fixMap)
    self.visitSegments(fixMap)
    self.visitPads(FixupPad(refs))
    self.visitVias(fixMap)
    RefCheck(refs)

  def add(self, mergee, mergeNets=[]):
    # check that there are no overlapping net-names
    err = False
    for netNam in mergee.getNetNames():
      if netNam in self.getNetNames() and not netNam in mergeNets:
        print("Net '{}' already preset".format( netNam ))
        err = True
    if err:
      raise RuntimeError("Duplicate net-names found; aborting")
    offset = len(self.getPcb()['net'])
    netMap = dict()
    for el in mergee.getPcb()['net']:
      if el._value[1] in mergeNets:
        # preserve net number in base
        try:
          netNo = self.getNetNames()[el._value[1]]._value[0]
        except KeyError:
          raise RuntimeError("Net '{}' to be merged not found in base module".format(el._value[1]))
      else:
        netNo = el._value[0] + offset
      netMap[el._value[0]] = netNo
    mergee.fixupNets( netMap )
    for cl in ['zone', 'net', 'segment', 'via', 'module']:
      for el in mergee.getPcb()[cl]:
        self.getPcb()[cl] = el

b = PCBPart('a.kicad_pcb')
RefVerify(b)
m = PCBPart('l')
RefVerify(m)
b.add(m,['""','+3V3','+5V','UART_RX_MIO14','UART_TX_MIO15'])

class A(object):
  def __init__(self):
    pass
  def __call__(self, nod, pat):
    print("{}: {}".format(".".join(pat), nod))

#m.visit(A())


b.export(sys.stdout,'  ')
