#!/usr/bin/env python3

from kicad_pcb import *
from sexp_parser import *
import sys
import getopt
import re
import io

outf   = None
mergef = None
basf   = None
mergen = []
anchor = []
logLvl = 'ERROR'
opts, args = getopt.getopt(sys.argv[1:], "hm:l:o:n:p:b:")
for o, a in opts:
  if o == '-h':
    print("merge two PCBs", file=sys.stderr)
  elif o == '-o':
    if not outf is None:
      raise RuntimeError("only one -o option permitted")
    outf = a
  elif o == '-b':
    if not basf is None:
      raise RuntimeError("only one -b option permitted")
    basf = a
  elif o == '-m':
    if not mergef is None:
      raise RuntimeError("only one -m option permitted")
    mergef = a
  elif o == '-l':
    lchoices = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if a in lchoices:
      logLvl = a
    else:
      print("-l value must be one of:", file=sys.stderr)
      for c in lchoices:
        print(c, file=sys.stderr)
      raise RuntimeError("Invalid logging level")
  elif o == '-n':
    mergen.append(a)
  elif o == '-p':
    anchor = a.split(':')
    if not len(anchor) in [1,2]:
      raise RuntimeError("path substitution must be '[from:]to'")

if basf is None:
  raise RuntimeError("Exactly one -b option (base PCB) required")

if mergef is None:
  raise RuntimeError("Exactly one -m option (mergee PCB) required")

logging.basicConfig(level=logLvl,
        format="%(filename)s:%(lineno)s: %(levelname)s - %(message)s")

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
          print("{} ({}) has '{}' but no ref found".format('.'.join(path), o, key), file=sys.sterr)
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
      print('Error: {}'.format(e), file=sys.stderr)
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

  def fixupPaths(self, anchor):
    if 0 == len(anchor):
      return
    pats = '^'
    repl = '/' + anchor[-1]
    if 1 < len(anchor):
      pats = '^/' + anchor[0]
    pat = re.compile(pats)
    for m in self.getPcb()['module']:
      # replace path (action=0)
      m._value.add(Sexp('path',pat.sub( repl, m['path'], 1)), action=0)

  @staticmethod
  def netClassEqual(nc1, nc2):
    if len(nc1) != len(nc2):
      return 0
    it = iter(nc2)
    next(it) # dont compare netclass name; caller decides whether that matter
    next(it) # ignore description
    r  = 1
    while True:
      try:
        k = next(it)
        print("comparing {} -- {}".format(nc1[k], nc2[k]), file=sys.stderr)
        if ( 'add_net' != k and nc1[k] != nc2[k] ):
          print("netclass ('{}') mismatch: values for '{}' differ".format(nc1[0], k), file=sys.stderr)
          r = 0
      except KeyError:
          print("netclass ('{}') key mismatch: '{}' not found".format(nc1[0], k), file=sys.stderr)
          r = 0
      except StopIteration:
          return r

  @staticmethod
  def findNetClass(netName, netClasses):
    for cls in netClasses:
      for net in cls['add_net']:
        if net._value == netName:
          return cls
    return None

  def hasNetClass(self, name):
    for ncl in self.getPcb()['net_class']:
      if ncl[0] == name:
        return ncl
    return None

  def checkNetClasses(self, mergee, mergeNets):
    for mnc in mergee.getPcb()['net_class']:
      for bnc in self.getPcb()['net_class']:
        if mnc[0] == bnc[0] and not self.netClassEqual(mnc, bnc):
          raise RuntimeError("Duplicate net-class with conflicting settings found: '{}'".format(bnc[0]))
    e = False
    for net in mergeNets:
      # current netclass
      mnc = self.findNetClass(net, mergee.getPcb()['net_class'])
      bnc = self.findNetClass(net,   self.getPcb()['net_class'])
      if ( bnc is None and mnc is None ):
        if net == '""':
          continue
        raise RuntimeError("net '{}' not in any netclass??".format(netName));
      if not self.netClassEqual(mnc, bnc):
        print("Cannot merge net '{}' -- member of incompatible netclasses".format(net), file=sys.stderr)
        e = True
    if e:
      raise RuntimeError("Incompatible Netclasses")

  def add(self, mergee, anchor, mergeNets=[]):
    # check that there are no overlapping net-names
    err = False
    for netNam in mergee.getNetNames():
      if netNam in self.getNetNames() and not netNam in mergeNets:
        print("Net '{}' already preset".format( netNam ), file=sys.stderr)
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
          raise RuntimeError("Net '{}' to be merged not found in base module".format(el._value[1]), file=sys.stderr)
      else:
        netNo  = offset
        offset = offset + 1
      netMap[el._value[0]] = netNo
    self.checkNetClasses( mergee, mergeNets )
    mergee.fixupNets( netMap )
    mergee.fixupPaths( anchor )
    # merge elements
    for cl in ['zone', 'net', 'segment', 'via', 'module', 'gr_line', 'gr_poly', 'gr_arc', 'gr_circle', 'gr_text']:
      for el in mergee.getPcb()[cl]:
        if cl != 'net' or not el._value[1] in mergeNets:
          self.getPcb()[cl] = el
    # merge net classes
    for ncl in mergee.getPcb()['net_class']:
      # if this class contains a merged net then we eliminate
      # it here since it is already a member of the base PCB's 
      # respective netclass
      for n in mergeNets:
        idx = 0
        for el in ncl['add_net']:
          if el._value == n:
            print("Eliminating {} from {}".format(n, ncl[0]), file=sys.stderr)
            del(ncl['add_net'][idx])
            # restart with next element of 'mergeNets'
            # don't rely on iterators here asl ncl['add_net']
            # has changed
            break
          idx = idx + 1
      # if a netclass with this name is not present then just
      # add this netclass
      bnc = self.hasNetClass( ncl[0] )
      if bnc is None:
        print("Adding net class '{}' to base PCB".format(ncl[0]), file=sys.stderr)
        self.getPcb()['net_class'] = ncl
      else:
        # merge nets into base PCB's netclass (we checked already
        # that it's properties are compatible
        for el in ncl['add_net']:
          print("Merging net '{}' into base PCB netclass '{}'".format(el._value, ncl[0]), file=sys.stderr)
          bnc['add_net'] = el

b = PCBPart(basf)
RefVerify(b)
m = PCBPart(mergef)
RefVerify(m)
b.add(m,anchor,mergen)

if not outf is None:
  if '-' == outf:
    f = sys.stdout
  else:
    f = io.open(outf,'w')
  b.export(f,'  ')
