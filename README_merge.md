# Merging two PCBs with `merge_pcb.py`

This script helps reinstantiating an existing "sub-PCB"
one or multiple times in a "super" or "containing" project.

It requires several manual manipulations during the
workflow.

The 'sub-PCB' must be added as a hierarchical sheet to the
super-project (in eeschema).

The sub-PCB is (manually) reannotated (in KiCAD) for each 
instantiation in the super-project and imported using the
`merge_pcb.py` script.

## Workflow

Several things have to be kept in sync by the script
 - 'normal' net names
 - global net names
 - locally labeled net names
 - net numbering inside the `kicad_pcb` file

Before you start real work make sure you have backups of
everything!

### Reannotate the Subproject

In order to seamlessly integrate the sub-PCB into the (super)
project the 'normal' net names must be unique and consistent
between the sub- and super-projects.

We can enforce this by a (somewhat cumbersome) procedure:

Open the sub-project in KiCAD and reannotate manually, 
completely resetting the existing annotation. If the
sub-project consists of multiple hierarchical sheets then
the sheet must be annotated recursively

 - select 'Use the current page only' or 'Entire schematic'
 - select 'Reset existing annotations'
 - select 'Recurse into subsheets'
 - select 'Use first free number after: X' using a sufficiently high
   number of X (higher than the biggest reference in the super project)

You will later repeat the re-annotation for the 2nd (and further)
instance(s) using different/higher numbers of 'X'.

### Update Sub-PCB

Next, use the 'Update PCB from Schematic' tool in pcbnew. Luckily,
pcbnew supports this reannotating across the two tools!

 - *unselect* `re-link footprints to schematic symbols based on their reference designators`

Also: this is a good moment to ensure that the sub-PCB does not
overlap the physical area occupied by the main PCB. Just move
the sub-PCB to a safe place away from the main PCB (which you
cannot see, of course; you may have to open the super-project
and check coordinates).

Save the PCB file.

We now have a schematic and PCB with known reference numbers that we
can import into the super-project.

### Save Sub-PCB Instance

Copy the sub-PCB to a unique name that identifies the instance

    cp sub.kicad_pcb  sub-inst1.kicad_pcb

### Instantiate Module in Super-Project Schematics

Now open the super-project in KiCAD and create a hierarchical
sheet for each instantiation of the module. Set the file name
to point to the top schematic of the sub-PCB.

Pick a *unique* sheet name (you'll need that later on).

At this point the new instance of the sub-module is not
annotated (yet).

### Annotate Module in Super-Project

We now must annotate the module instance in the super-project
with numbers that are 'reproducible' and match what we did above.

In principal we would enter each hierarchical sheet representing
an instance of the sub-project and

 - select 'Use the current page only'.
 - select 'Reset existing annotations'
 - make sure all the other options (including the starting number 'X')
   match the settings used when annotating the sub-project.   

Unfortunately, however, KiCAD (at least version 7.0.1) would not
produce an annotation that exactly mirrors the sub-project
annotation. This then prevents `merge_pcb.py` from making the
correct associations.

For this reason the `reannotate.py` script was created. It implements
propagating sub-project annotations to the super project.

Close the KiCAD project and run the script (giving the unique
sheet name you used above):

     reannotate.py -b <top_project> -m <sub_sheet_name> -r

Note that this modifies all sub-project files - make sure to
have backup copies in place! The arguments are the super- *project*
and sub-project *sheet* names, respectively, and not schematics file
names. The project name is equivalent to the top schematics file's base name.

At this point we have:

 - super-project schematic with a new instance of the module and 
   reference numbers that match the sub-project.
 - super-project PCB file.
 - sub-project PCB file with reference numbers that match the
   instances of the module in the super-project.

### Repeat for all Instances

Repeat the steps of
  1. re-annotating all sheets of sub-project with a new, unique number 'X'
     chosen so that all references used by the sub-project do not collide
     with any number in other instances of the sub-project nor the super-project.
  2. update sub-PCB from Schematic.
  3. save and copy to a separate `sub-inst<y>.kicad_pcb` file.
  4. add a new instance of the sub-project to the super-project giving it
     a unique sheet name.
  5. reannotate the super-project using the newly added sub-project sheet name.

## Merge the Sub-PCB Instances into the Main-PCB

Use the `merge_pcb.py` script to merge the sub-PCB files
into the main PCB (after saving the original):

1. make sure no PCB is open in KiCAD

2. backup the original main PCB:

     cp main.kicad_pcb main.kicad_pcb.orig

3. create a working copy

     mv main.kicad_pcb main.kicad_pcb.wrk

4. Determine info: The script needs to know some information
   that is not present in the `kicad_pcb` file and which you
   have to retrieve manually:

     - Sheet name
     - Sheet UUID (some hex number; can be printed by `reannotate.py -b <main-project-name> -m <sub-sheet-name>`)

5. run the script (the files passed to -b, -m are not
   modified):

     merge_pcb.py -b main.kicad_pcb.wrk -m sub-inst1.kicad_pcb -o main.kicad_pcb -p <uuid> -s <sheet_name>

   which writes the newly merged PCB into `main.kicad_pcb`.

   Note that it is not possible to modify a file 'in-place', so
   -b and -o must not point to the same file.

   Use '-s' and '-p' to communicate the sheet name and uuid
   of the module instance to the script.

6. The script will most likely fail, reporting nets which are present
   in both designs. These are in most cases global nets that connect
   to power, such as 'GND' or '+3V3'.
   You can tell the script that it is OK to connect such nets together
   by passing their names using '-n' (one option for each net):

      -n '"+5V"' -n '"GND"'

   If you encounter global nets which are not OK to connect then
   you must rename them either in the super- or sub-project.

7. Another cause of failure is when properties of net-classes
   do not match between designs. You must resolve such conflicts
   by modifying the respective properties in either the super-
   or sub-design.

8. Once conflicts are resolved the new PCB can be opened in
   KiCAD and should show the 1rst instance of the submodule
   (no second instance yet!).

   If you create more instances then you should move the first
   one away (physically) because the next instance will be placed
   at exactly the same location and save the PCB.

9. Now you repeat steps 3.-8. for each instance:

    - new working copy of the augmented PCB
    - determine instance sheet name and timestamp in super-
      schematic; update -s and -p settings accordingly.
    - use `-m` for next `kicad_pcb` sub-module instantiation

10. Once you have all instances you try to 'Update PCB from Schematics'
   and hopefully that will leave all components in place and pass
   a DRC leaving only a rats-nest for you to connect the sub-designs.

   You may have to

     - *select* `re-link footprints to schematic symbols based on their reference designators`

   for this to work.
