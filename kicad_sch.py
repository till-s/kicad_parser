from sexp_parser import *
import re

# Support reannotating a main-project that uses a sub-project so that
# references in the main-project exactly match their counter-parts
# in the sub-project.
# Ideally, this could be achieved in kicad itself:
#   1. open sub-project;
#   2. reannotate (use 'reset annotations', 'recurse into subsheets',
#      order, high starting number, e.g., 1000)
#   3. save, exit
#   4. open main-project
#   5. add sub-project as a sub-sheet
#   6. open sub-project sheet
#   7. reannotate *current sheet* with all the other settings
#      identical to 2.
#   8. save, exit.
#
# Unfortunately, when doing this in kicad-7.0.11 the annotations did
# NOT exactly match, i.e., some symbols would be assigned *different*
# references which makes using the 'merge_pcb' script impossible.

# The 'KicadSch.reannotate()' method implements the desired behaviour.

# Helper class to hold main- and sub-project
#  - name
#  - 'path'
class Map:
  def __init__(self, prjname, path, filename):
    self._name_ = prjname
    self._path_ = path.replace('"','')
    self._patt_ = re.compile('^' + self._path)
    self._fnam_ = filename

  @property
  def _name(self):
    return self._name_

  @property
  def _path(self):
    return self._path_

  @property
  def _patt(self):
    return self._patt_

  @property
  def _fileName(self):
    return self._fnam_


class KicadSch(SexpParser):

  # entries under 'instances' are permanent; new ones are created
  # whenever this sheet is instantiated as a sub-sheet of some other
  # sheet (the last statement applies recursively).
  # This method purges all entries and restores the sheet to a state
  # where it is not the subsheet of anything.
  # If 'pre' is a string then this method will recurse into
  # all subsheets and write the purged sheet to 'pre' + 'filename'.
  # NOTE: this method should not be invoked directly but via the
  #       static 'purgeInstances()' method.
  def _purgeInstances(self, pre=None):
    for k in ['symbol', 'sheet']:
      try:
        l = self[k]
      except KeyError:
        continue
      for el in l:
          el._value.pop('instances')
          if ( not pre is None and k == 'sheet' ):
             for p in el['property']:
               if p[0].strip('"') == 'Sheetfile':
                  KicadSch.purgeInstances(p[1].strip('"'), pre)

  # recursively get the names of all sub-sheets; returns
  # a unique list of sheet file names; should not be invoked
  # directly but from the static 'getSheets()' method
  def _getSheets(self):
    sheetList = list()
    try:
      l = self['sheet']
    except KeyError:
      return sheetList
    for el in l:
      for p in el['property']:
        if p[0].strip('"') == 'Sheetfile':
          fnam = p[1].strip('"')
          if not fnam in sheetList:
            sheetList.append(fnam)
          sheetList.extend( KicadSch.load(fnam)._getSheets() )
          break
    return sheetList

  # ensure that a Sexp is a SexpList - this allows
  # us to always use an iteration w/o further checking
  # if the Sexp is actually a list.
  @staticmethod
  def mkList(x):
    if not isinstance(x, SexpList):
      x = SexpList(x)
    return x

  @staticmethod
  def matchNameOrUUID(prj, aname, auuid):
    # print('matchNameOrUUID {} {}'.format(aname,auuid))
    name=prj[0].strip('"')
    if ( len(name) > 0 ):
       # print('checking against name'.format(name))
       return name == aname
    auuid=auuid.strip('"')
    for p in KicadSch.mkList(prj['path']):
      uuid = p[0].split('/')[1].strip('"')
      # print('checking against uuid {}'.format(uuid))
      if ( auuid == uuid ):
        return True
    return False

  @staticmethod
  def matchMap(prj,amap):
    auuid = amap._path.split('/')[1]
    return KicadSch.matchNameOrUUID(prj, amap._name, auuid)

  # copy references as used in one project ('src') to another project ('dst')
  # Note that a symbol may be instantiated by many projects and on multiple
  # subsheets. Every instance is identified by a unique 'path' which describes
  # the sheet hierarchy to get to the symbol instantiation.
  #
  # We have to
  #   1. identify the instantiations that belong to the 'src' project.
  #      They must have paths that start with the top-level sheet's UUID.
  #       'src._patt' is a regexp describing this. Because the 'src' project
  #      may instantiate a sheet multiple times there may be multiple paths
  #      but all must begin with the 'src' projects top-level path.
  #
  #      E.g.,
  #
  #          <src-prj-uuid>/a/b/c   : 1st. instance
  #          <src-prj-uuid>/d/e     : 2nd. instance
  #
  #   2. For every instantiation in the 'src' project we must identify
  #      a matching instantiation in the 'dst' project that becomes the target
  #      of our operation.
  #      The initial path of these instantiations is the 'dst' project's
  #      path to the sub-project's top sheet:
  #          dst-path = <dst-prj-uuid>/<sub-prj-sheet>/
  #
  #      =>  <src-prj-uuid>/a/b/c  copy ref to  <dst-path>/a/b/c
  #      =>  <src-prj-uuid>/d/e    copy ref to  <dst-path>/d/e
  #
  def copyRefs(self, src, dst):
    try:
      syms = self['symbol']
    except KeyError:
      return
    # make sure it's a SexpList
    syms = self.mkList(syms)
    for sym in syms:
      # Debug: print main reference of this symbol (not of any sheet instance)
      #for p in sym['property']:
      #  if ( p[0].strip('"') == 'Reference' ):
      #    print(p[1])
      #    break
      srcprj = None
      dstprj = None
      prjlst = sym['instances']['project']
      if (not isinstance(prjlst, SexpList)):
        raise RuntimeError("'project' is not a list - forgot to annotate parent project?")
      # find 'src' and 'dst' projects by name; i.e., only look at
      # all instantiations belonging to these projects (note that
      # there may still be e.g., stale instances from some sheet instantiations
      # that were present at some time in any of these projects but no longer
      # exist - their paths will still be present in 'instances' and we will
      # filter them below...
      for prj in prjlst:
        if self.matchMap(prj, src):
          # 'from' project name found; record this project
          srcprj = prj
        elif ( self.matchMap(prj, dst) ):
          # 'dst' project name found; record this project
          dstprj = prj
        if not srcprj is None and not dstprj is None:
          # we have found the 'src' and 'dst' projects and their 'path's
          # hold *all* instances (including e.g., stale ones, see above)
          srcpath = self.mkList( srcprj['path'] )
          dstpath = self.mkList( dstprj['path'] )
          for elsrc in srcpath:
            # filter paths that match the 'from' pattern
            replacement = src._patt.subn( dst._path, elsrc[0].strip('"') )
            # Debugging
            # print("replacement {}".format(replacement))
            if ( replacement[1] == 1 ):
              # successful replacement, i.e., the from path matches 'el'
              # now find the matching 'dst' path which is associated with
              # the 'src'
              for eldst in dstpath:
                if ( eldst[0].strip('"') == replacement[0] ):
                  # Debugging
                  # print("Match; {} => {}".format(elsrc[0], eldst[0]))
                  for k,v in elsrc._value.items():
                    if k != 0:
                      # Debugging
                      # print("replacing {}: {} -> {}".format(k, eldst[k], v))

                      # action '0' replaces (otherwise item is added to a list)
                      eldst._value.add(v, 0)
                  break
          break
      if (srcprj is None):
         raise RuntimeError("src project {} not found in {}".format(src._path, src._fileName))
      if (dstprj is None):
         raise RuntimeError("dst project {} not found".format(dst._path))

  # recursively look for sub_sheet_name in 'file_name' and it's subsheets
  # while recording the UUIDs that lead there
  @staticmethod
  def getSubsheetUUIDPath(uuid_list, file_name, sub_sheet_name):
    instantiator = None
    asch         = KicadSch.load(file_name)
    try:
      sheetList    = KicadSch.mkList( asch['sheet'] )
    except KeyError:
      return None
    for sheet in sheetList:
      sheet_name = None
      sheet_file = None
      for p in sheet['property']:
        if p[0].strip('"') == 'Sheetname':
          sheet_name = p[1].strip('"')
        elif p[0].strip('"') == 'Sheetfile':
          sheet_file = p[1].strip('"')
      if ( sheet_file is None ):
        msg = "getSubsheetUUIDPath: sheet in file {} has no associated file".format(file_name)
        raise RuntimeError(msg)
      if ( sheet_name is None ):
        msg = "getSubsheetUUIDPath: sheet in file {} has no name".format(file_name)
      uuid_list.append( sheet['uuid'].strip('"') )
      if ( sub_sheet_name == sheet_name ):
        return sheet_file
      else:
        subsheet_file = KicadSch.getSubsheetUUIDPath(uuid_list, sheet_file, sub_sheet_name)
        if ( not subsheet_file is None ):
          # found
          return subsheet_file
      # nothing found; pop this UUD
      del( uuid_list[-1] )
    return None
  

  # determine paths of subproject
  #   - when subproject is the top
  #   - when main-project is the top
  def mkMaps(self, main_name, sub_sheet_name):
    uuid_path  = [ self['uuid'] ]
    main_file  = KicadSch.mkSchFileName( main_name )
    sheet_file = KicadSch.getSubsheetUUIDPath( uuid_path, main_file, sub_sheet_name )
    if ( sheet_file is None ):
      msg = "Unable to locate sheet '{}'".format(sub_sheet_name)
      raise RuntimeError(msg)
    sub_name = re.sub("[.].*", "", sheet_file)
    src = Map( sub_name, '/' + KicadSch.load(sheet_file)['uuid'].strip('"'), sheet_file )
    dst = Map( main_name, '/' + '/'.join( uuid_path ), main_file )
    return src, dst

  def export(self, out, indent='  '):
    exportSexp(self, out, '', indent)

  @staticmethod
  def load(fn):
    with open(fn,'r') as f:
      return KicadSch(parseSexp(f.read()))

  # See _purgeInstances()
  @staticmethod
  def purgeInstances(fn, pre='new/'):
    sub = KicadSch.load(fn)
    sub._purgeInstances(pre)
    with open(pre+fn, 'w') as f:
      sub.export(f)

  # Recursively obtain a unique list of all sheets used/referenced
  # by a sheet with file name 'fn'. Unique means that any sub-sheet that
  # is referenced multiple times appears only once in the result.
  @staticmethod
  def getSheets(fn):
    sheetList= [fn]
    sheetList.extend( KicadSch.load(fn)._getSheets() )
    return sheetList

  @staticmethod
  def mkSchFileName(prj_name):
    return prj_name + '.kicad_sch'

  # Obtain the subproject prefix that can be used by 'merge_pcb'  (-p option)
  @staticmethod
  def getMergePcbPrefix(main_name, sub_sheet_name):
    src,dst = KicadSch.load(KicadSch.mkSchFileName(main_name)).mkMaps(main_name, sub_sheet_name)
    return dst._path.split('/')[-1]

  # Reannotate a 'main' project using references from a 'sub' project.
  #       1. sub-project has unique annotations (e.g., with numbers starting
  #          at 1000).
  #       2. sub-project's top sheet is instantiated as sub-sheet in
  #          main-project. sub-project cannot be a hierarchy; this is not
  #          supported ATM).
  @staticmethod
  def reannotate(main_name, sub_sheet_name):
    src,dst = KicadSch.load(KicadSch.mkSchFileName(main_name)).mkMaps(main_name, sub_sheet_name)
    files = KicadSch.getSheets(src._fileName)
    for f in files:
      sch = KicadSch.load(f)
      try:
        sch.copyRefs(src, dst)
      except Exception as e:
        print("copyRefs failed for {}".format(f))
        raise(e)
        
      with open(f, 'w') as f:
        sch.export(f)
