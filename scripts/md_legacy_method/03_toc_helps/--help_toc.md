# Table of Contents
- [Transform options:](#transform-options:)
- [Other options:](#other-options:)
- [Print options are processed in the following order:](#print-options-are-processed-in-the-following-order:)

## Transform options:

```
--align-xy X,Y      Align the model to the given point.
 --center X,Y        Center the print around the given center.
 --cut N             Cut model at the given Z.
 --delete-after-load ABCD
                     Delete files after loading.
 --dont-arrange      Do not rearrange the given models before merging and keep their original XY
                     coordinates.
 --duplicate N       Multiply copies by this factor.
 --duplicate-grid X,Y
                     Multiply copies by creating a grid.
 --ensure-on-bed     Lift the object above the bed when it is partially below. Enabled by default,
                     use --no-ensure-on-bed to disable.
 --merge, -m         Arrange the supplied models in a plate and merge them in a single model in order
                     to perform actions once.
 --repair            Try to repair any non-manifold meshes (this option is implicitly added whenever
                     we need to slice the model to perform the requested action).
 --rotate N          Rotation angle around the Z axis in degrees.
 --rotate-x N        Rotation angle around the X axis in degrees.
 --rotate-y N        Rotation angle around the Y axis in degrees.
 --scale N           Scaling factor or percentage.
 --scale-to-fit X,Y,Z
                     Scale to fit the given volume.
 --split             Detect unconnected parts in the given model(s) and split them into separate
                     objects.
```

## Other options:

```
--config-compatibility
                     This version of PrusaSlicer may not understand configurations produced by the
                     newest PrusaSlicer versions. For example, newer PrusaSlicer may extend the list
                     of supported firmware flavors. One may decide to bail out or to substitute an
                     unknown value with a default silently or verbosely. (disable, enable,
                     enable_silent; default: enable)
 --datadir ABCD      Load and store settings at the given directory. This is useful for maintaining
                     different profiles or including configurations from a network storage.
 --ignore-nonexistent-config
                     Do not fail if a file supplied to --load does not exist.
 --load ABCD         Load configuration from the specified file. It can be used more than once to
                     load options from multiple files.
 --loglevel N        Sets logging sensitivity. 0:fatal, 1:error, 2:warning, 3:info, 4:debug, 5:trace
                     For example. loglevel=2 logs fatal, error and warning level messages.
 --material-profile ABCD
                     Name(s) of the material preset(s) used for slicing. Could be filaments or
                     sla_material preset name(s) depending on printer tochnology
 --output ABCD, -o ABCD
                     The file where the output will be written (if not specified, it will be based on
                     the input file).
 --print-profile ABCD
                     Name of the print preset used for slicing.
 --printer-profile ABCD
                     Name of the printer preset used for slicing.
 --single-instance   If enabled, the command line arguments are sent to an existing instance of GUI
                     PrusaSlicer, or an existing PrusaSlicer window is activated. Overrides the
                     "single_instance" configuration value from application preferences.
 --sw-renderer       Render with a software renderer. The bundled MESA software renderer is loaded
                     instead of the default OpenGL driver.
 --threads N         Sets the maximum number of threads the slicing process will use. If not defined,
                     it will be decided automatically.
```

## Print options are processed in the following order:

```
1) Config keys from the command line, for example --fill-pattern=stars
	   (highest priority, overwrites everything below)
	2) Config files loaded with --load
	3) Config values loaded from amf or 3mf files

Run --help-fff / --help-sla to see the full listing of print options.
```