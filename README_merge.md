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
each sheet must be annotated individually
 - select 'Use the current page only'
 - select 'Reset existing annotations'
 - select 'Use first free number after: X'
 - *unselect* `re-link footprints to schematic symbols based on their reference designators`
Repeat this process for every sheet, choosing 'X' so that
the numbers don't overlap between sheets nor the main project.

E.g., assume you want to instantiate a module which consists
of two hierarchical sheets twice in the super-project.
You may e.g., pick the following number ranges:
 - below 1000: base project
 - 1000..1099 1st sheet of sub-module, 1st instance in base project
 - 1100..1199 2nd sheet of sub-module, 1st instance in base project
 - 2000..2099 1st sheet of sub-module, 2st instance in base project
 - 2100..2199 2nd sheet of sub-module, 2st instance in base project

You would thus select 'X=1000' for the first sheet and 'X=1100'
for the second sheet. Proceed with re-annotating the sheets (in
the sub-project) in the described way and save the eeschema file.

You will later repeat the re-annotation for the 2nd (and further)
instance(s) using X=2000 and X=2100, respectively, etc.

### Update Sub-PCB
Next, use the 'Update PCB from Schematic' tool in pcbnew. Luckily,
pcbnew supports this reannotating across the two tools!

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

### Repeat for all Instances
Repeat the steps of
  1. re-annotating all sheets of sub-project 
  2. update sub-PCB from Schematic
  3. save and copy to a separate `sub-inst<y>.kicad_pcb` file

### Instantiate Module(s) in Super-Project Schematics
Now open the super-project in KiCAD and create a hierarchical
sheet for each instantiation of the module. Set the file name
to point to the top schematic of the sub-PCB.

Pick a sheet name (or use the default).

Repeat this for each instance of the sub-module you want to
create.

At this point the new instance(s) of the sub-module are not
annotated (yet).

### Annotate Module(s) in Super-Project
We now must annotate the module instance(s) in the super-project
with numbers that are 'reproducible' and match what we did above.

Enter the hierarchical sheet(s) and manually annotate the
sheets in exactly the same way you did it in the sub-project
*using the same starting numbers on matching sheets*.

- on the first  sheet of the first  instance use X=1000
- on the second sheet of the first  instance use X=1100
- on the first  sheet of the second instance use X=2000
- on the second sheet of the second instance use X=2100

(The exact numbers don't matter -- as long as they match what you
did in the sub-project and are unique).

Make sure you select the options to only annotate the current
sheet, to reset the annotation and use the correct starting number
each time.

Save the schematic.

At this point we have:
 - super-project schematic with several instances of the module and 
   reference numbers that match the sub-project.
 - super-project PCB file.
 - sub-project PCB file(s) with reference numbers that match the
   instances of the module in the super-project.

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

   open 'Schematic Sheet Properties' *of the instance you are merging* and note:
     - Sheet name
     - Unique timestamp (some hex number)

5. run the script (the files passed to -b, -m are not
   modified):

     merge_pcb.py -b main.kicad_pcb.wrk -m sub-inst1.kicad_pcb -o main.kicad_pcb -p <unique-timestamp> -s <sheet_name>

   which writes the newly merged PCB into `main.kicad_pcb`.

   Note that it is not possible to modify a file 'in-place', so
   -b and -o must not point to the same file.

   Use '-s' and '-p' to communicate the sheet name and timestamp
   of the module instance to the script.

6. The script will most likely fail, reporting nets which are present
   in both designs. These are in most cases global nets that connect
   to power, such as 'GND' or '+3V3'.
   You can tell the script that it is OK to connect such nets together
   by passing their names using '-n' (one option for each net):

      -n '+5V' -n 'GND'

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
